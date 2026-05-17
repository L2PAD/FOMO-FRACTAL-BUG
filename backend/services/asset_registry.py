"""
FOMO Asset Universe / Registry
Single source of truth for all supported assets.
Maps internal symbols → CoinGecko IDs, exchange symbols, labels, categories.
"""

# Each asset entry:
# symbol: Internal canonical symbol (e.g., "BTC")
# name: Display name
# coingecko_id: CoinGecko API identifier
# category: For grouping in UI
# rank: For default sort order (approx market cap rank)
# binance: Binance spot symbol (informational)
# bybit: Bybit symbol (informational)

ASSET_UNIVERSE = [
    # === Layer 1 / Major ===
    {"symbol": "BTC",  "name": "Bitcoin",      "coingecko_id": "bitcoin",        "category": "layer1", "rank": 1,  "binance": "BTCUSDT",  "bybit": "BTCUSDT"},
    {"symbol": "ETH",  "name": "Ethereum",     "coingecko_id": "ethereum",       "category": "layer1", "rank": 2,  "binance": "ETHUSDT",  "bybit": "ETHUSDT"},
    {"symbol": "BNB",  "name": "BNB",          "coingecko_id": "binancecoin",    "category": "layer1", "rank": 4,  "binance": "BNBUSDT",  "bybit": "BNBUSDT"},
    {"symbol": "SOL",  "name": "Solana",       "coingecko_id": "solana",         "category": "layer1", "rank": 5,  "binance": "SOLUSDT",  "bybit": "SOLUSDT"},
    {"symbol": "XRP",  "name": "XRP",          "coingecko_id": "ripple",         "category": "layer1", "rank": 6,  "binance": "XRPUSDT",  "bybit": "XRPUSDT"},
    {"symbol": "ADA",  "name": "Cardano",      "coingecko_id": "cardano",        "category": "layer1", "rank": 8,  "binance": "ADAUSDT",  "bybit": "ADAUSDT"},
    {"symbol": "AVAX", "name": "Avalanche",    "coingecko_id": "avalanche-2",    "category": "layer1", "rank": 12, "binance": "AVAXUSDT", "bybit": "AVAXUSDT"},
    {"symbol": "DOT",  "name": "Polkadot",     "coingecko_id": "polkadot",       "category": "layer1", "rank": 13, "binance": "DOTUSDT",  "bybit": "DOTUSDT"},
    {"symbol": "NEAR", "name": "NEAR Protocol","coingecko_id": "near",           "category": "layer1", "rank": 18, "binance": "NEARUSDT", "bybit": "NEARUSDT"},
    {"symbol": "SUI",  "name": "Sui",          "coingecko_id": "sui",            "category": "layer1", "rank": 20, "binance": "SUIUSDT",  "bybit": "SUIUSDT"},
    {"symbol": "APT",  "name": "Aptos",        "coingecko_id": "aptos",          "category": "layer1", "rank": 25, "binance": "APTUSDT",  "bybit": "APTUSDT"},
    {"symbol": "ATOM", "name": "Cosmos",       "coingecko_id": "cosmos",         "category": "layer1", "rank": 27, "binance": "ATOMUSDT", "bybit": "ATOMUSDT"},

    # === DeFi / Layer 2 ===
    {"symbol": "LINK", "name": "Chainlink",    "coingecko_id": "chainlink",      "category": "defi",   "rank": 14, "binance": "LINKUSDT", "bybit": "LINKUSDT"},
    {"symbol": "UNI",  "name": "Uniswap",      "coingecko_id": "uniswap",        "category": "defi",   "rank": 22, "binance": "UNIUSDT",  "bybit": "UNIUSDT"},
    {"symbol": "ARB",  "name": "Arbitrum",      "coingecko_id": "arbitrum",       "category": "layer2", "rank": 35, "binance": "ARBUSDT",  "bybit": "ARBUSDT"},
    {"symbol": "OP",   "name": "Optimism",      "coingecko_id": "optimism",       "category": "layer2", "rank": 40, "binance": "OPUSDT",   "bybit": "OPUSDT"},

    # === Meme / Culture ===
    {"symbol": "DOGE", "name": "Dogecoin",     "coingecko_id": "dogecoin",       "category": "meme",   "rank": 7,  "binance": "DOGEUSDT", "bybit": "DOGEUSDT"},
    {"symbol": "PEPE", "name": "Pepe",         "coingecko_id": "pepe",           "category": "meme",   "rank": 24, "binance": "PEPEUSDT", "bybit": "PEPEUSDT"},

    # === Infra / Storage ===
    {"symbol": "FIL",  "name": "Filecoin",     "coingecko_id": "filecoin",       "category": "infra",  "rank": 30, "binance": "FILUSDT",  "bybit": "FILUSDT"},
    {"symbol": "LTC",  "name": "Litecoin",     "coingecko_id": "litecoin",       "category": "layer1", "rank": 19, "binance": "LTCUSDT",  "bybit": "LTCUSDT"},
]

# Quick lookup dicts
_BY_SYMBOL = {a["symbol"]: a for a in ASSET_UNIVERSE}
_BY_COINGECKO = {a["coingecko_id"]: a for a in ASSET_UNIVERSE}


def get_all_assets() -> list[dict]:
    """Return all supported assets sorted by rank."""
    return sorted(ASSET_UNIVERSE, key=lambda a: a["rank"])


def get_asset(symbol: str) -> dict | None:
    """Look up asset by symbol (case-insensitive, handles BTCUSDT format)."""
    key = normalize_symbol(symbol)
    return _BY_SYMBOL.get(key)


def normalize_symbol(raw: str) -> str:
    """
    Normalize any asset reference to our internal symbol.
    Handles: BTC, btc, BTCUSDT, btcusdt, bitcoin (coingecko id)
    """
    if not raw:
        return "BTC"
    
    clean = raw.strip().upper()
    
    # Direct match
    if clean in _BY_SYMBOL:
        return clean
    
    # Strip USDT/USD/PERP suffix
    for suffix in ("USDT", "USD", "PERP", "BUSD"):
        if clean.endswith(suffix):
            base = clean[:-len(suffix)]
            if base in _BY_SYMBOL:
                return base
    
    # Try CoinGecko ID (lowercase)
    lower = raw.strip().lower()
    if lower in _BY_COINGECKO:
        return _BY_COINGECKO[lower]["symbol"]
    
    # Default fallback
    return "BTC"


def get_coingecko_id(symbol: str) -> str:
    """Get CoinGecko API ID for a symbol."""
    asset = get_asset(symbol)
    return asset["coingecko_id"] if asset else "bitcoin"


def is_supported(symbol: str) -> bool:
    """Check if an asset is in our universe."""
    return normalize_symbol(symbol) in _BY_SYMBOL


def search_assets(query: str) -> list[dict]:
    """Search assets by symbol or name prefix."""
    if not query:
        return get_all_assets()
    
    q = query.strip().upper()
    q_lower = query.strip().lower()
    
    results = []
    for a in ASSET_UNIVERSE:
        if (a["symbol"].startswith(q) or 
            a["name"].upper().startswith(q) or
            q_lower in a["name"].lower()):
            results.append(a)
    
    return sorted(results, key=lambda a: a["rank"])


def get_categories() -> dict[str, list[dict]]:
    """Group assets by category."""
    cats: dict[str, list[dict]] = {}
    for a in sorted(ASSET_UNIVERSE, key=lambda x: x["rank"]):
        cat = a["category"]
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(a)
    return cats
