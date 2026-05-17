"""
Entities V2 — Foundation Seed Data
====================================
Real Ethereum addresses for major entities.
Sources: Etherscan labels, Arkham, public disclosures.
"""

ENTITY_SEED = [
    # ── EXCHANGES ──
    {
        "name": "Binance",
        "slug": "binance",
        "type": "exchange",
        "category": "CEX",
        "confidence": 98,
        "description": "World's largest cryptocurrency exchange by trading volume",
        "tags": ["cex", "top10", "global", "derivatives"],
        "addresses": [
            {"address": "0x28c6c06298d514db089934071355e5743bf21d60", "chain": "ethereum", "role": "hot_wallet", "confidence": 98, "source": "verified"},
            {"address": "0x21a31ee1afc51d94c2efccaa2092ad1028285549", "chain": "ethereum", "role": "hot_wallet", "confidence": 95, "source": "verified"},
            {"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d", "chain": "ethereum", "role": "hot_wallet", "confidence": 95, "source": "verified"},
            {"address": "0x56eddb7aa87536c09ccc2793473599fd21a8b17f", "chain": "ethereum", "role": "cold_wallet", "confidence": 90, "source": "tagged"},
            {"address": "0xf977814e90da44bfa03b6295a0616a897441acec", "chain": "ethereum", "role": "cold_wallet", "confidence": 95, "source": "verified"},
        ],
    },
    {
        "name": "Coinbase",
        "slug": "coinbase",
        "type": "exchange",
        "category": "CEX",
        "confidence": 98,
        "description": "Largest US-regulated cryptocurrency exchange, NASDAQ-listed",
        "tags": ["cex", "top10", "us", "regulated", "public"],
        "addresses": [
            {"address": "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43", "chain": "ethereum", "role": "hot_wallet", "confidence": 98, "source": "verified"},
            {"address": "0x71660c4005ba85c37ccec55d0c4493e66fe775d3", "chain": "ethereum", "role": "hot_wallet", "confidence": 95, "source": "verified"},
            {"address": "0x503828976d22510aad0201ac7ec88293211d23da", "chain": "ethereum", "role": "cold_wallet", "confidence": 90, "source": "tagged"},
            {"address": "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740", "chain": "ethereum", "role": "cold_wallet", "confidence": 90, "source": "tagged"},
        ],
    },
    {
        "name": "Kraken",
        "slug": "kraken",
        "type": "exchange",
        "category": "CEX",
        "confidence": 95,
        "description": "Major US-based cryptocurrency exchange, founded 2011",
        "tags": ["cex", "top10", "us", "established"],
        "addresses": [
            {"address": "0x2910543af39aba0cd09dbb2d50200b3e800a63d2", "chain": "ethereum", "role": "hot_wallet", "confidence": 95, "source": "verified"},
            {"address": "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0", "chain": "ethereum", "role": "hot_wallet", "confidence": 90, "source": "tagged"},
        ],
    },
    {
        "name": "OKX",
        "slug": "okx",
        "type": "exchange",
        "category": "CEX",
        "confidence": 95,
        "description": "Global cryptocurrency exchange, formerly OKEx",
        "tags": ["cex", "top10", "global", "derivatives"],
        "addresses": [
            {"address": "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b", "chain": "ethereum", "role": "hot_wallet", "confidence": 95, "source": "verified"},
            {"address": "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3", "chain": "ethereum", "role": "hot_wallet", "confidence": 90, "source": "tagged"},
        ],
    },
    {
        "name": "Bybit",
        "slug": "bybit",
        "type": "exchange",
        "category": "CEX",
        "confidence": 90,
        "description": "Major derivatives exchange",
        "tags": ["cex", "derivatives", "global"],
        "addresses": [
            {"address": "0xf89d7b9c864f589bbf53a82105107622b35eaa40", "chain": "ethereum", "role": "hot_wallet", "confidence": 90, "source": "tagged"},
        ],
    },
    {
        "name": "Gate.io",
        "slug": "gate-io",
        "type": "exchange",
        "category": "CEX",
        "confidence": 88,
        "description": "Global cryptocurrency exchange",
        "tags": ["cex", "global", "altcoins"],
        "addresses": [
            {"address": "0x0d0707963952f2fba59dd06f2b425ace40b492fe", "chain": "ethereum", "role": "hot_wallet", "confidence": 88, "source": "tagged"},
        ],
    },

    # ── FUNDS ──
    {
        "name": "a16z Crypto",
        "slug": "a16z",
        "type": "fund",
        "category": "VC",
        "confidence": 85,
        "description": "Andreessen Horowitz crypto venture fund",
        "tags": ["vc", "tier1", "defi", "infrastructure"],
        "addresses": [
            {"address": "0x05e793ce0c6027323ac150f6d45c2344d28b6571", "chain": "ethereum", "role": "treasury", "confidence": 85, "source": "public"},
            {"address": "0x7a16ff8270133f063aab6c9977183d9e72835428", "chain": "ethereum", "role": "staking", "confidence": 80, "source": "heuristic"},
        ],
    },
    {
        "name": "Paradigm",
        "slug": "paradigm",
        "type": "fund",
        "category": "VC",
        "confidence": 82,
        "description": "Crypto-native investment firm",
        "tags": ["vc", "tier1", "defi", "research"],
        "addresses": [
            {"address": "0xd4e96ef8eee8678dbff4d535e033ed1a4f7605b7", "chain": "ethereum", "role": "treasury", "confidence": 82, "source": "public"},
        ],
    },
    {
        "name": "Grayscale",
        "slug": "grayscale",
        "type": "fund",
        "category": "Institution",
        "confidence": 90,
        "description": "Largest digital currency asset manager",
        "tags": ["institution", "etf", "btc", "eth"],
        "addresses": [
            {"address": "0xa2f987a546d4cd1c607ee8141276876c26b72bdf", "chain": "ethereum", "role": "cold_wallet", "confidence": 88, "source": "public"},
        ],
    },

    # ── MARKET MAKERS ──
    {
        "name": "Jump Trading",
        "slug": "jump-trading",
        "type": "market_maker",
        "category": "MM",
        "confidence": 85,
        "description": "Major quantitative trading and market-making firm",
        "tags": ["mm", "hft", "liquidity", "institutional"],
        "addresses": [
            {"address": "0x9507c04b10486547584c37bcbd931b2a4fee9a41", "chain": "ethereum", "role": "trading", "confidence": 85, "source": "heuristic"},
            {"address": "0xf584f8728b874a6a5c7a8d4d387c9aae9172d621", "chain": "ethereum", "role": "trading", "confidence": 80, "source": "heuristic"},
        ],
    },
    {
        "name": "Wintermute",
        "slug": "wintermute",
        "type": "market_maker",
        "category": "MM",
        "confidence": 90,
        "description": "Algorithmic market maker for digital assets",
        "tags": ["mm", "defi", "liquidity", "institutional"],
        "addresses": [
            {"address": "0x00000000ae347930bd1aa7dc7eb29a952c8b2e36", "chain": "ethereum", "role": "trading", "confidence": 90, "source": "verified"},
            {"address": "0xdbf5e9c5206d0db70a90108bf936da60221dc080", "chain": "ethereum", "role": "trading", "confidence": 85, "source": "tagged"},
        ],
    },

    # ── PROTOCOLS ──
    {
        "name": "Uniswap Protocol",
        "slug": "uniswap",
        "type": "protocol",
        "category": "DEX",
        "confidence": 98,
        "description": "Leading decentralized exchange protocol",
        "tags": ["dex", "defi", "amm", "top_protocol"],
        "addresses": [
            {"address": "0x1a9c8182c09f50c8318d769245bea52c32be35bc", "chain": "ethereum", "role": "treasury", "confidence": 95, "source": "verified"},
        ],
    },
    {
        "name": "Lido Finance",
        "slug": "lido",
        "type": "protocol",
        "category": "DeFi",
        "confidence": 95,
        "description": "Largest liquid staking protocol",
        "tags": ["staking", "defi", "lsd", "top_protocol"],
        "addresses": [
            {"address": "0x3e40d73eb977dc6a537af587d48316fee66e9c8c", "chain": "ethereum", "role": "treasury", "confidence": 95, "source": "verified"},
        ],
    },
    {
        "name": "Aave Protocol",
        "slug": "aave",
        "type": "protocol",
        "category": "DeFi",
        "confidence": 95,
        "description": "Leading decentralized lending protocol",
        "tags": ["lending", "defi", "top_protocol"],
        "addresses": [
            {"address": "0x464c71f6c2f760dda6093dcb91c24c39e5d6e18c", "chain": "ethereum", "role": "treasury", "confidence": 95, "source": "verified"},
        ],
    },

    # ── WHALES ──
    {
        "name": "Whale Cluster Alpha",
        "slug": "whale-alpha",
        "type": "whale",
        "category": "Unknown",
        "confidence": 60,
        "description": "Unidentified high-volume cluster, accumulation pattern",
        "tags": ["whale", "unknown", "high_volume"],
        "addresses": [
            {"address": "0x00000000219ab540356cbb839cbe05303d7705fa", "chain": "ethereum", "role": "unknown", "confidence": 60, "source": "clustered"},
        ],
    },
]
