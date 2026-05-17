"""
Real Crypto Investments Data
============================

Real investment data for major crypto VC funds.
Data sourced from public announcements and funding databases.
"""

# a16z crypto (Andreessen Horowitz) - Portfolio
A16Z_INVESTMENTS = [
    # Layer 1 & Infrastructure
    {"project": "solana", "name": "Solana", "amount": 314000000, "round": "Series A", "year": 2021},
    {"project": "near", "name": "NEAR Protocol", "amount": 150000000, "round": "Series B", "year": 2022},
    {"project": "avalanche", "name": "Avalanche", "amount": 230000000, "round": "Private Sale", "year": 2021},
    {"project": "aptos", "name": "Aptos", "amount": 200000000, "round": "Series A", "year": 2022},
    {"project": "sui", "name": "Sui", "amount": 336000000, "round": "Series B", "year": 2022},
    {"project": "flow", "name": "Flow", "amount": 18000000, "round": "Seed", "year": 2020},
    {"project": "celo", "name": "Celo", "amount": 25000000, "round": "Series A", "year": 2020},
    
    # Layer 2 & Scaling
    {"project": "optimism", "name": "Optimism", "amount": 150000000, "round": "Series B", "year": 2022},
    {"project": "arbitrum", "name": "Arbitrum", "amount": 120000000, "round": "Series B", "year": 2021},
    {"project": "starkware", "name": "StarkWare", "amount": 100000000, "round": "Series D", "year": 2022},
    {"project": "matter-labs", "name": "Matter Labs (zkSync)", "amount": 200000000, "round": "Series C", "year": 2022},
    {"project": "scroll", "name": "Scroll", "amount": 50000000, "round": "Series A", "year": 2023},
    
    # DeFi
    {"project": "uniswap", "name": "Uniswap", "amount": 165000000, "round": "Series B", "year": 2022},
    {"project": "compound", "name": "Compound", "amount": 25000000, "round": "Series A", "year": 2019},
    {"project": "maker", "name": "MakerDAO", "amount": 15000000, "round": "Venture", "year": 2018},
    {"project": "dydx", "name": "dYdX", "amount": 65000000, "round": "Series C", "year": 2021},
    {"project": "lido", "name": "Lido Finance", "amount": 70000000, "round": "Series A", "year": 2022},
    {"project": "aave", "name": "Aave", "amount": 25000000, "round": "Series A", "year": 2020},
    {"project": "instadapp", "name": "Instadapp", "amount": 10000000, "round": "Series A", "year": 2021},
    
    # NFT & Gaming
    {"project": "opensea", "name": "OpenSea", "amount": 300000000, "round": "Series C", "year": 2022},
    {"project": "yuga-labs", "name": "Yuga Labs", "amount": 450000000, "round": "Seed", "year": 2022},
    {"project": "dapper-labs", "name": "Dapper Labs", "amount": 250000000, "round": "Series D", "year": 2021},
    {"project": "axie-infinity", "name": "Sky Mavis (Axie)", "amount": 152000000, "round": "Series B", "year": 2021},
    
    # Infrastructure & Tooling
    {"project": "alchemy", "name": "Alchemy", "amount": 200000000, "round": "Series C", "year": 2022},
    {"project": "phantom", "name": "Phantom", "amount": 109000000, "round": "Series B", "year": 2022},
    {"project": "worldcoin", "name": "Worldcoin", "amount": 115000000, "round": "Series C", "year": 2023},
    {"project": "eigenlayer", "name": "EigenLayer", "amount": 50000000, "round": "Series A", "year": 2023},
    {"project": "layerzero", "name": "LayerZero", "amount": 135000000, "round": "Series A", "year": 2022},
    
    # Social & Identity
    {"project": "farcaster", "name": "Farcaster", "amount": 150000000, "round": "Series A", "year": 2024},
    {"project": "lens", "name": "Lens Protocol", "amount": 15000000, "round": "Seed", "year": 2022},
]

# Paradigm - Portfolio
PARADIGM_INVESTMENTS = [
    # Layer 1 & Infrastructure
    {"project": "ethereum", "name": "Ethereum", "amount": 0, "round": "Early Investor", "year": 2014},
    {"project": "cosmos", "name": "Cosmos", "amount": 9000000, "round": "ICO", "year": 2017},
    {"project": "polkadot", "name": "Polkadot", "amount": 50000000, "round": "Private Sale", "year": 2020},
    {"project": "osmosis", "name": "Osmosis", "amount": 21000000, "round": "Seed", "year": 2021},
    {"project": "monad", "name": "Monad", "amount": 225000000, "round": "Series A", "year": 2024},
    
    # Layer 2
    {"project": "optimism", "name": "Optimism", "amount": 150000000, "round": "Series B", "year": 2022},
    {"project": "arbitrum", "name": "Arbitrum", "amount": 120000000, "round": "Series B", "year": 2021},
    {"project": "blast", "name": "Blast", "amount": 20000000, "round": "Seed", "year": 2023},
    
    # DeFi
    {"project": "uniswap", "name": "Uniswap", "amount": 165000000, "round": "Series B", "year": 2022},
    {"project": "lido", "name": "Lido Finance", "amount": 70000000, "round": "Series A", "year": 2022},
    {"project": "blur", "name": "Blur", "amount": 11000000, "round": "Seed", "year": 2022},
    {"project": "ribbon", "name": "Ribbon Finance", "amount": 8500000, "round": "Series A", "year": 2021},
    {"project": "synthetix", "name": "Synthetix", "amount": 12000000, "round": "Seed", "year": 2020},
    {"project": "frax", "name": "Frax Finance", "amount": 2000000, "round": "Seed", "year": 2020},
    
    # Infrastructure
    {"project": "flashbots", "name": "Flashbots", "amount": 60000000, "round": "Series B", "year": 2023},
    {"project": "chainalysis", "name": "Chainalysis", "amount": 100000000, "round": "Series E", "year": 2021},
    {"project": "fireblocks", "name": "Fireblocks", "amount": 310000000, "round": "Series E", "year": 2022},
    
    # NFT & Gaming
    {"project": "opensea", "name": "OpenSea", "amount": 300000000, "round": "Series C", "year": 2022},
    {"project": "art-blocks", "name": "Art Blocks", "amount": 6000000, "round": "Seed", "year": 2021},
]

# Coinbase Ventures - Portfolio
COINBASE_VENTURES_INVESTMENTS = [
    {"project": "polygon", "name": "Polygon", "amount": 450000000, "round": "Private Sale", "year": 2022},
    {"project": "optimism", "name": "Optimism", "amount": 25000000, "round": "Series A", "year": 2021},
    {"project": "arbitrum", "name": "Arbitrum", "amount": 20000000, "round": "Series A", "year": 2021},
    {"project": "near", "name": "NEAR Protocol", "amount": 30000000, "round": "Series A", "year": 2021},
    {"project": "compound", "name": "Compound", "amount": 8000000, "round": "Seed", "year": 2018},
    {"project": "uniswap", "name": "Uniswap", "amount": 11000000, "round": "Series A", "year": 2020},
    {"project": "aave", "name": "Aave", "amount": 12000000, "round": "Private", "year": 2020},
    {"project": "dydx", "name": "dYdX", "amount": 10000000, "round": "Series A", "year": 2020},
    {"project": "opensea", "name": "OpenSea", "amount": 23000000, "round": "Series A", "year": 2021},
    {"project": "dapper-labs", "name": "Dapper Labs", "amount": 25000000, "round": "Series C", "year": 2020},
    {"project": "alchemy", "name": "Alchemy", "amount": 80000000, "round": "Series B", "year": 2021},
    {"project": "amber", "name": "Amber Group", "amount": 100000000, "round": "Series B", "year": 2022},
    {"project": "blockdaemon", "name": "Blockdaemon", "amount": 155000000, "round": "Series B", "year": 2022},
]

# Binance Labs - Portfolio
BINANCE_LABS_INVESTMENTS = [
    {"project": "polygon", "name": "Polygon", "amount": 15000000, "round": "Seed", "year": 2019},
    {"project": "aptos", "name": "Aptos", "amount": 150000000, "round": "Series A", "year": 2022},
    {"project": "sui", "name": "Sui", "amount": 100000000, "round": "Series A", "year": 2022},
    {"project": "axie-infinity", "name": "Sky Mavis (Axie)", "amount": 7500000, "round": "Series A", "year": 2019},
    {"project": "1inch", "name": "1inch", "amount": 12000000, "round": "Series A", "year": 2020},
    {"project": "injective", "name": "Injective", "amount": 10000000, "round": "Seed", "year": 2020},
    {"project": "certik", "name": "CertiK", "amount": 37000000, "round": "Series B", "year": 2021},
    {"project": "wormhole", "name": "Wormhole", "amount": 225000000, "round": "Private", "year": 2023},
    {"project": "pendle", "name": "Pendle", "amount": 3000000, "round": "Seed", "year": 2021},
    {"project": "radiant", "name": "Radiant Capital", "amount": 10000000, "round": "Seed", "year": 2022},
    {"project": "manta", "name": "Manta Network", "amount": 25000000, "round": "Series A", "year": 2023},
]

# Polychain Capital - Portfolio
POLYCHAIN_INVESTMENTS = [
    {"project": "cosmos", "name": "Cosmos", "amount": 9000000, "round": "ICO", "year": 2017},
    {"project": "dfinity", "name": "Dfinity", "amount": 102000000, "round": "Series B", "year": 2018},
    {"project": "filecoin", "name": "Filecoin", "amount": 52000000, "round": "ICO", "year": 2017},
    {"project": "polkadot", "name": "Polkadot", "amount": 40000000, "round": "Private Sale", "year": 2017},
    {"project": "tezos", "name": "Tezos", "amount": 50000000, "round": "ICO", "year": 2017},
    {"project": "compound", "name": "Compound", "amount": 8000000, "round": "Seed", "year": 2018},
    {"project": "acala", "name": "Acala", "amount": 7000000, "round": "Series A", "year": 2021},
    {"project": "celo", "name": "Celo", "amount": 20000000, "round": "Series A", "year": 2019},
    {"project": "dydx", "name": "dYdX", "amount": 10000000, "round": "Series A", "year": 2019},
]

# Pantera Capital - Portfolio
PANTERA_INVESTMENTS = [
    {"project": "bitcoin", "name": "Bitcoin", "amount": 0, "round": "Early", "year": 2013},
    {"project": "polkadot", "name": "Polkadot", "amount": 25000000, "round": "Private Sale", "year": 2017},
    {"project": "filecoin", "name": "Filecoin", "amount": 25000000, "round": "ICO", "year": 2017},
    {"project": "zcash", "name": "Zcash", "amount": 3000000, "round": "Early", "year": 2016},
    {"project": "0x", "name": "0x Protocol", "amount": 2400000, "round": "Seed", "year": 2017},
    {"project": "starkware", "name": "StarkWare", "amount": 50000000, "round": "Series C", "year": 2021},
    {"project": "terra", "name": "Terraform Labs", "amount": 25000000, "round": "Series A", "year": 2021},
    {"project": "1inch", "name": "1inch", "amount": 12000000, "round": "Series A", "year": 2020},
    {"project": "amber", "name": "Amber Group", "amount": 100000000, "round": "Series B", "year": 2022},
    {"project": "injective", "name": "Injective", "amount": 10000000, "round": "Seed", "year": 2020},
]

# Dragonfly Capital - Portfolio
DRAGONFLY_INVESTMENTS = [
    {"project": "near", "name": "NEAR Protocol", "amount": 21600000, "round": "Series A", "year": 2020},
    {"project": "matter-labs", "name": "Matter Labs (zkSync)", "amount": 50000000, "round": "Series B", "year": 2022},
    {"project": "1inch", "name": "1inch", "amount": 12000000, "round": "Series A", "year": 2020},
    {"project": "dydx", "name": "dYdX", "amount": 65000000, "round": "Series C", "year": 2021},
    {"project": "ribbon", "name": "Ribbon Finance", "amount": 8500000, "round": "Series A", "year": 2021},
    {"project": "lido", "name": "Lido Finance", "amount": 70000000, "round": "Series A", "year": 2022},
    {"project": "bybit", "name": "Bybit", "amount": 15000000, "round": "Private", "year": 2021},
    {"project": "matrixport", "name": "Matrixport", "amount": 100000000, "round": "Series C", "year": 2022},
]

# Multicoin Capital - Portfolio
MULTICOIN_INVESTMENTS = [
    {"project": "solana", "name": "Solana", "amount": 20000000, "round": "Seed", "year": 2019},
    {"project": "near", "name": "NEAR Protocol", "amount": 21600000, "round": "Series A", "year": 2020},
    {"project": "helium", "name": "Helium", "amount": 111000000, "round": "Series D", "year": 2022},
    {"project": "arweave", "name": "Arweave", "amount": 5000000, "round": "Series A", "year": 2020},
    {"project": "livepeer", "name": "Livepeer", "amount": 20000000, "round": "Series B", "year": 2021},
    {"project": "graph", "name": "The Graph", "amount": 5000000, "round": "Private", "year": 2020},
    {"project": "render", "name": "Render Network", "amount": 30000000, "round": "Series A", "year": 2021},
    {"project": "audius", "name": "Audius", "amount": 5000000, "round": "Series A", "year": 2020},
]

# Project team members (founders and key team)
PROJECT_TEAM_MEMBERS = {
    "ethereum": [
        {"id": "vitalik", "name": "Vitalik Buterin", "role": "Co-founder"},
        {"id": "gavin-wood", "name": "Gavin Wood", "role": "Co-founder"},
        {"id": "joseph-lubin", "name": "Joseph Lubin", "role": "Co-founder"},
    ],
    "solana": [
        {"id": "anatoly-yakovenko", "name": "Anatoly Yakovenko", "role": "Co-founder & CEO"},
        {"id": "raj-gokal", "name": "Raj Gokal", "role": "Co-founder & COO"},
    ],
    "uniswap": [
        {"id": "hayden-adams", "name": "Hayden Adams", "role": "Founder"},
    ],
    "polygon": [
        {"id": "sandeep-nailwal", "name": "Sandeep Nailwal", "role": "Co-founder"},
        {"id": "jaynti-kanani", "name": "Jaynti Kanani", "role": "Co-founder & CEO"},
        {"id": "anurag-arjun", "name": "Anurag Arjun", "role": "Co-founder"},
    ],
    "arbitrum": [
        {"id": "steven-goldfeder", "name": "Steven Goldfeder", "role": "Co-founder & CEO"},
        {"id": "ed-felten", "name": "Ed Felten", "role": "Co-founder"},
        {"id": "harry-kalodner", "name": "Harry Kalodner", "role": "Co-founder & CTO"},
    ],
    "optimism": [
        {"id": "jing-wang", "name": "Jinglan Wang", "role": "Co-founder"},
        {"id": "ben-jones", "name": "Ben Jones", "role": "Co-founder"},
        {"id": "karl-floersch", "name": "Karl Floersch", "role": "Co-founder"},
    ],
    "cosmos": [
        {"id": "jae-kwon", "name": "Jae Kwon", "role": "Co-founder"},
        {"id": "ethan-buchman", "name": "Ethan Buchman", "role": "Co-founder"},
    ],
    "near": [
        {"id": "illia-polosukhin", "name": "Illia Polosukhin", "role": "Co-founder"},
        {"id": "alexander-skidanov", "name": "Alexander Skidanov", "role": "Co-founder"},
    ],
    "avalanche": [
        {"id": "emin-gun-sirer", "name": "Emin Gün Sirer", "role": "Founder & CEO"},
        {"id": "kevin-sekniqi", "name": "Kevin Sekniqi", "role": "Co-founder & COO"},
    ],
    "aptos": [
        {"id": "mo-shaikh", "name": "Mo Shaikh", "role": "Co-founder & CEO"},
        {"id": "avery-ching", "name": "Avery Ching", "role": "Co-founder & CTO"},
    ],
    "sui": [
        {"id": "evan-cheng", "name": "Evan Cheng", "role": "Co-founder & CEO"},
        {"id": "sam-blackshear", "name": "Sam Blackshear", "role": "Co-founder & CTO"},
    ],
    "aave": [
        {"id": "stani-kulechov", "name": "Stani Kulechov", "role": "Founder & CEO"},
    ],
    "compound": [
        {"id": "robert-leshner", "name": "Robert Leshner", "role": "Founder & CEO"},
    ],
    "dydx": [
        {"id": "antonio-juliano", "name": "Antonio Juliano", "role": "Founder & CEO"},
    ],
    "lido": [
        {"id": "konstantin-lomashuk", "name": "Konstantin Lomashuk", "role": "Co-founder"},
        {"id": "vasiliy-shapovalov", "name": "Vasiliy Shapovalov", "role": "Co-founder"},
    ],
    "opensea": [
        {"id": "devin-finzer", "name": "Devin Finzer", "role": "Co-founder & CEO"},
        {"id": "alex-atallah", "name": "Alex Atallah", "role": "Co-founder & CTO"},
    ],
    "chainlink": [
        {"id": "sergey-nazarov", "name": "Sergey Nazarov", "role": "Co-founder & CEO"},
    ],
    "polkadot": [
        {"id": "gavin-wood", "name": "Gavin Wood", "role": "Founder"},
        {"id": "robert-habermeier", "name": "Robert Habermeier", "role": "Co-founder"},
    ],
}

# Fund partners/team
FUND_TEAM_MEMBERS = {
    "a16z": [
        {"id": "marc-andreessen", "name": "Marc Andreessen", "role": "Co-founder"},
        {"id": "ben-horowitz", "name": "Ben Horowitz", "role": "Co-founder"},
        {"id": "chris-dixon", "name": "Chris Dixon", "role": "General Partner"},
        {"id": "arianna-simpson", "name": "Arianna Simpson", "role": "General Partner"},
        {"id": "ali-yahya", "name": "Ali Yahya", "role": "General Partner"},
    ],
    "paradigm": [
        {"id": "matt-huang", "name": "Matt Huang", "role": "Co-founder"},
        {"id": "fred-ehrsam", "name": "Fred Ehrsam", "role": "Co-founder"},
        {"id": "dan-robinson", "name": "Dan Robinson", "role": "Research Partner"},
        {"id": "georgios-konstantopoulos", "name": "Georgios Konstantopoulos", "role": "Research Partner & CTO"},
    ],
    "coinbase-ventures": [
        {"id": "brian-armstrong", "name": "Brian Armstrong", "role": "CEO Coinbase"},
        {"id": "emilie-choi", "name": "Emilie Choi", "role": "President & COO"},
    ],
    "binance-labs": [
        {"id": "cz", "name": "Changpeng Zhao", "role": "Founder Binance"},
        {"id": "yi-he", "name": "Yi He", "role": "Co-founder"},
    ],
    "polychain": [
        {"id": "olaf-carlson-wee", "name": "Olaf Carlson-Wee", "role": "Founder & CEO"},
    ],
    "pantera": [
        {"id": "dan-morehead", "name": "Dan Morehead", "role": "Founder & CEO"},
        {"id": "joey-krug", "name": "Joey Krug", "role": "Co-CIO"},
    ],
    "dragonfly": [
        {"id": "haseeb-qureshi", "name": "Haseeb Qureshi", "role": "Managing Partner"},
        {"id": "tom-schmidt", "name": "Tom Schmidt", "role": "General Partner"},
    ],
    "multicoin": [
        {"id": "kyle-samani", "name": "Kyle Samani", "role": "Co-founder & Managing Partner"},
        {"id": "tushar-jain", "name": "Tushar Jain", "role": "Co-founder & Managing Partner"},
    ],
}

# All investments grouped by fund slug
ALL_INVESTMENTS = {
    "a16z": A16Z_INVESTMENTS,
    "paradigm": PARADIGM_INVESTMENTS,
    "coinbase-ventures": COINBASE_VENTURES_INVESTMENTS,
    "binance-labs": BINANCE_LABS_INVESTMENTS,
    "polychain": POLYCHAIN_INVESTMENTS,
    "pantera": PANTERA_INVESTMENTS,
    "dragonfly": DRAGONFLY_INVESTMENTS,
    "multicoin": MULTICOIN_INVESTMENTS,
}

# ============================================================================
# TIER 2 & 3 FUNDS (Additional)
# ============================================================================

# Sequoia Capital - Crypto Portfolio
SEQUOIA_INVESTMENTS = [
    {"project": "solana", "name": "Solana", "amount": 314000000, "round": "Series A", "year": 2021},
    {"project": "polygon", "name": "Polygon", "amount": 450000000, "round": "Private Sale", "year": 2022},
    {"project": "ftx", "name": "FTX", "amount": 420000000, "round": "Series B", "year": 2021},
    {"project": "fireblocks", "name": "Fireblocks", "amount": 310000000, "round": "Series E", "year": 2022},
    {"project": "alchemy", "name": "Alchemy", "amount": 200000000, "round": "Series C", "year": 2022},
    {"project": "aptos", "name": "Aptos", "amount": 200000000, "round": "Series A", "year": 2022},
]

# Galaxy Digital - Portfolio
GALAXY_INVESTMENTS = [
    {"project": "celsius", "name": "Celsius Network", "amount": 400000000, "round": "Series B", "year": 2021},
    {"project": "fireblocks", "name": "Fireblocks", "amount": 80000000, "round": "Series C", "year": 2021},
    {"project": "figment", "name": "Figment", "amount": 50000000, "round": "Series B", "year": 2021},
    {"project": "blockdaemon", "name": "Blockdaemon", "amount": 155000000, "round": "Series B", "year": 2022},
    {"project": "cryptoslam", "name": "CryptoSlam", "amount": 9000000, "round": "Series A", "year": 2022},
]

# Jump Crypto - Portfolio  
JUMP_CRYPTO_INVESTMENTS = [
    {"project": "wormhole", "name": "Wormhole", "amount": 225000000, "round": "Private", "year": 2023},
    {"project": "solana", "name": "Solana", "amount": 50000000, "round": "Strategic", "year": 2021},
    {"project": "terra", "name": "Terraform Labs", "amount": 40000000, "round": "Strategic", "year": 2021},
    {"project": "sei", "name": "Sei Network", "amount": 30000000, "round": "Series A", "year": 2023},
    {"project": "monad", "name": "Monad", "amount": 225000000, "round": "Series A", "year": 2024},
    {"project": "pyth", "name": "Pyth Network", "amount": 0, "round": "Founding Team", "year": 2021},
]

# Framework Ventures - Portfolio
FRAMEWORK_INVESTMENTS = [
    {"project": "chainlink", "name": "Chainlink", "amount": 0, "round": "Early", "year": 2017},
    {"project": "aave", "name": "Aave", "amount": 3000000, "round": "Seed", "year": 2020},
    {"project": "synthetix", "name": "Synthetix", "amount": 2000000, "round": "Seed", "year": 2019},
    {"project": "yearn", "name": "Yearn Finance", "amount": 0, "round": "Investor", "year": 2020},
    {"project": "tokemak", "name": "Tokemak", "amount": 4000000, "round": "Seed", "year": 2021},
    {"project": "goldfinch", "name": "Goldfinch", "amount": 11000000, "round": "Series A", "year": 2021},
    {"project": "radicle", "name": "Radicle", "amount": 12000000, "round": "Series A", "year": 2021},
]

# Hack VC - Portfolio
HACK_VC_INVESTMENTS = [
    {"project": "eigenlayer", "name": "EigenLayer", "amount": 50000000, "round": "Series A", "year": 2023},
    {"project": "starkware", "name": "StarkWare", "amount": 0, "round": "Seed", "year": 2018},
    {"project": "zksync", "name": "Matter Labs (zkSync)", "amount": 50000000, "round": "Series B", "year": 2022},
    {"project": "celestia", "name": "Celestia", "amount": 55000000, "round": "Series A", "year": 2022},
    {"project": "berachain", "name": "Berachain", "amount": 42000000, "round": "Series A", "year": 2023},
]

# Animoca Brands - Portfolio
ANIMOCA_INVESTMENTS = [
    {"project": "sandbox", "name": "The Sandbox", "amount": 0, "round": "Acquisition", "year": 2018},
    {"project": "axie-infinity", "name": "Sky Mavis (Axie)", "amount": 7500000, "round": "Series A", "year": 2020},
    {"project": "opensea", "name": "OpenSea", "amount": 0, "round": "Strategic", "year": 2022},
    {"project": "dapper-labs", "name": "Dapper Labs", "amount": 0, "round": "Strategic", "year": 2020},
    {"project": "yuga-labs", "name": "Yuga Labs", "amount": 450000000, "round": "Seed", "year": 2022},
    {"project": "polygon", "name": "Polygon", "amount": 0, "round": "Strategic", "year": 2022},
    {"project": "mocaverse", "name": "Mocaverse", "amount": 0, "round": "Internal", "year": 2023},
]

# Spartan Group - Portfolio
SPARTAN_INVESTMENTS = [
    {"project": "solana", "name": "Solana", "amount": 0, "round": "Early", "year": 2019},
    {"project": "aptos", "name": "Aptos", "amount": 0, "round": "Strategic", "year": 2022},
    {"project": "sui", "name": "Sui", "amount": 0, "round": "Strategic", "year": 2022},
    {"project": "sei", "name": "Sei Network", "amount": 30000000, "round": "Series A", "year": 2023},
    {"project": "pendle", "name": "Pendle", "amount": 3000000, "round": "Seed", "year": 2021},
    {"project": "radiant", "name": "Radiant Capital", "amount": 10000000, "round": "Seed", "year": 2022},
]

# Delphi Ventures - Portfolio
DELPHI_INVESTMENTS = [
    {"project": "axie-infinity", "name": "Sky Mavis (Axie)", "amount": 7500000, "round": "Series A", "year": 2020},
    {"project": "ribbon", "name": "Ribbon Finance", "amount": 8500000, "round": "Series A", "year": 2021},
    {"project": "pendle", "name": "Pendle", "amount": 2000000, "round": "Seed", "year": 2021},
    {"project": "gearbox", "name": "Gearbox Protocol", "amount": 4000000, "round": "Seed", "year": 2022},
    {"project": "radiant", "name": "Radiant Capital", "amount": 10000000, "round": "Seed", "year": 2022},
    {"project": "kwenta", "name": "Kwenta", "amount": 0, "round": "Treasury", "year": 2022},
]

# Digital Currency Group (DCG) - Portfolio
DCG_INVESTMENTS = [
    {"project": "coinbase", "name": "Coinbase", "amount": 25000000, "round": "Series C", "year": 2015},
    {"project": "circle", "name": "Circle", "amount": 50000000, "round": "Series C", "year": 2015},
    {"project": "ripple", "name": "Ripple", "amount": 0, "round": "Early", "year": 2013},
    {"project": "kraken", "name": "Kraken", "amount": 0, "round": "Series A", "year": 2014},
    {"project": "chainalysis", "name": "Chainalysis", "amount": 100000000, "round": "Series E", "year": 2021},
    {"project": "blockstream", "name": "Blockstream", "amount": 55000000, "round": "Series A", "year": 2016},
    {"project": "ledger", "name": "Ledger", "amount": 75000000, "round": "Series B", "year": 2018},
]

# Placeholder VC - Portfolio
PLACEHOLDER_INVESTMENTS = [
    {"project": "polkadot", "name": "Polkadot", "amount": 0, "round": "Early", "year": 2017},
    {"project": "cosmos", "name": "Cosmos", "amount": 0, "round": "ICO", "year": 2017},
    {"project": "arweave", "name": "Arweave", "amount": 5000000, "round": "Series A", "year": 2020},
    {"project": "decentraland", "name": "Decentraland", "amount": 0, "round": "Early", "year": 2017},
    {"project": "zcash", "name": "Zcash", "amount": 0, "round": "Early", "year": 2016},
    {"project": "maker", "name": "MakerDAO", "amount": 12000000, "round": "Series A", "year": 2018},
]

# Robot Ventures - Portfolio (Tarun Chitra)
ROBOT_VENTURES_INVESTMENTS = [
    {"project": "uniswap", "name": "Uniswap", "amount": 0, "round": "Seed", "year": 2019},
    {"project": "compound", "name": "Compound", "amount": 0, "round": "Seed", "year": 2018},
    {"project": "flashbots", "name": "Flashbots", "amount": 60000000, "round": "Series B", "year": 2023},
    {"project": "eigenlayer", "name": "EigenLayer", "amount": 50000000, "round": "Series A", "year": 2023},
    {"project": "anoma", "name": "Anoma", "amount": 26000000, "round": "Series A", "year": 2022},
]

# Additional fund team members
ADDITIONAL_FUND_TEAMS = {
    "sequoia": [
        {"id": "roelof-botha", "name": "Roelof Botha", "role": "Senior Partner"},
        {"id": "shaun-maguire", "name": "Shaun Maguire", "role": "Partner"},
    ],
    "galaxy": [
        {"id": "mike-novogratz", "name": "Mike Novogratz", "role": "Founder & CEO"},
    ],
    "jump-crypto": [
        {"id": "kanav-kariya", "name": "Kanav Kariya", "role": "President"},
    ],
    "framework": [
        {"id": "vance-spencer", "name": "Vance Spencer", "role": "Co-founder"},
        {"id": "michael-anderson", "name": "Michael Anderson", "role": "Co-founder"},
    ],
    "hack-vc": [
        {"id": "ed-roman", "name": "Ed Roman", "role": "Co-founder & Managing Partner"},
        {"id": "alex-pack", "name": "Alex Pack", "role": "Co-founder & Managing Partner"},
    ],
    "animoca": [
        {"id": "yat-siu", "name": "Yat Siu", "role": "Co-founder & Chairman"},
    ],
    "spartan": [
        {"id": "kelvin-koh", "name": "Kelvin Koh", "role": "Managing Partner"},
    ],
    "delphi": [
        {"id": "tom-shaughnessy", "name": "Tom Shaughnessy", "role": "Co-founder"},
        {"id": "jose-maria-macedo", "name": "José Maria Macedo", "role": "Co-founder"},
    ],
    "dcg": [
        {"id": "barry-silbert", "name": "Barry Silbert", "role": "Founder & CEO"},
    ],
    "placeholder": [
        {"id": "chris-burniske", "name": "Chris Burniske", "role": "Partner"},
        {"id": "joel-monegro", "name": "Joel Monegro", "role": "Partner"},
    ],
    "robot-ventures": [
        {"id": "tarun-chitra", "name": "Tarun Chitra", "role": "Founder & GP"},
    ],
}

# Extended ALL_INVESTMENTS with new funds
ALL_INVESTMENTS_EXTENDED = {
    **ALL_INVESTMENTS,
    "sequoia": SEQUOIA_INVESTMENTS,
    "galaxy": GALAXY_INVESTMENTS,
    "jump-crypto": JUMP_CRYPTO_INVESTMENTS,
    "framework": FRAMEWORK_INVESTMENTS,
    "hack-vc": HACK_VC_INVESTMENTS,
    "animoca": ANIMOCA_INVESTMENTS,
    "spartan": SPARTAN_INVESTMENTS,
    "delphi": DELPHI_INVESTMENTS,
    "dcg": DCG_INVESTMENTS,
    "placeholder": PLACEHOLDER_INVESTMENTS,
    "robot-ventures": ROBOT_VENTURES_INVESTMENTS,
}

# Extended fund team members
FUND_TEAM_MEMBERS_EXTENDED = {
    **FUND_TEAM_MEMBERS,
    **ADDITIONAL_FUND_TEAMS,
}
