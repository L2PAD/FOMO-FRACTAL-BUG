"""
Event Classifier — detects market type from question text.

Types:
  - price_threshold: "Will BTC be above 125k?"
  - direction_bet: "Bitcoin Up or Down - March 30"
  - etf_catalyst: "Will X ETF be approved?"
  - listing_catalyst: "Will X list on Binance?"
  - launch_catalyst: "Will X launch mainnet?"
  - token_launch: "Will X launch a token?"
  - unknown: unrecognized
"""
import re


KNOWN_ENTITIES = [
    "btc", "eth", "sol", "xrp", "doge", "ada", "bnb", "avax", "matic",
    "link", "uni", "aave", "arb", "op", "sui", "apt", "sei", "near",
    "binance", "coinbase", "blackrock", "sec", "grayscale", "fidelity",
    "vaneck", "bitwise", "21shares", "ark", "invesco",
]

ASSET_MAP = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
    "xrp": "XRP", "ripple": "XRP",
    "doge": "DOGE", "dogecoin": "DOGE",
    "cardano": "ADA", "ada": "ADA",
    "bnb": "BNB", "avax": "AVAX", "avalanche": "AVAX",
    "matic": "MATIC", "polygon": "MATIC",
    "link": "LINK", "chainlink": "LINK",
    "uni": "UNI", "uniswap": "UNI",
    "aave": "AAVE", "arb": "ARB", "arbitrum": "ARB",
    "op": "OP", "optimism": "OP",
    "sui": "SUI", "apt": "APT", "aptos": "APT",
    "sei": "SEI", "near": "NEAR",
    "usdt": "USDT", "usdc": "USDC", "tether": "USDT",
}


def classify(question: str) -> dict:
    """
    Classify a Polymarket question into market type.

    Returns dict with: event_type, asset, threshold, comparator, entities, tags, market_type
    """
    q = question.lower().strip()

    # --- Direction bet: "Bitcoin Up or Down", "Ethereum Up or Down" ---
    dir_match = re.search(r"(bitcoin|btc|ethereum|eth|solana|sol|xrp|doge|bnb|ada)\s+up\s+or\s+down", q)
    if dir_match:
        token_raw = dir_match.group(1)
        asset = ASSET_MAP.get(token_raw, token_raw.upper())
        return {
            "event_type": "direction_bet",
            "market_type": "quant",
            "asset": asset,
            "threshold": None,
            "comparator": "direction",
            "entities": [asset],
            "tags": ["crypto", "direction", asset.lower()],
        }

    # --- Price threshold: BTC ---
    btc_match = re.search(r"(?:bitcoin|btc).*?(?:above|below|over|under|reach|hit|dip)\s*(?:to\s*)?\$?([\d,]+(?:\.\d+)?)", q)
    if btc_match or ("bitcoin" in q and re.search(r"\$?([\d,]{5,})", q)):
        m = btc_match or re.search(r"\$?([\d,]{5,})", q)
        threshold = float(m.group(1).replace(",", ""))
        comp = "below" if any(w in q for w in ("below", "under", "dip")) else "above"
        return {
            "event_type": "price_threshold",
            "market_type": "quant",
            "asset": "BTC",
            "threshold": threshold,
            "comparator": comp,
            "entities": ["BTC"],
            "tags": ["crypto", "threshold", "btc"],
        }

    # --- Price threshold: ETH ---
    eth_match = re.search(r"(?:ethereum|eth).*?(?:above|below|over|under|reach|hit|dip)\s*(?:to\s*)?\$?([\d,]+(?:\.\d+)?)", q)
    if eth_match or ("ethereum" in q and re.search(r"\$?([\d,]{3,})", q)):
        m = eth_match or re.search(r"\$?([\d,]{3,})", q)
        threshold = float(m.group(1).replace(",", ""))
        comp = "below" if any(w in q for w in ("below", "under", "dip")) else "above"
        return {
            "event_type": "price_threshold",
            "market_type": "quant",
            "asset": "ETH",
            "threshold": threshold,
            "comparator": comp,
            "entities": ["ETH"],
            "tags": ["crypto", "threshold", "eth"],
        }

    # --- Price threshold: SOL ---
    sol_match = re.search(r"(?:solana|sol).*?(?:above|below|over|under|reach|hit|dip)\s*(?:to\s*)?\$?([\d,]+(?:\.\d+)?)", q)
    if sol_match:
        threshold = float(sol_match.group(1).replace(",", ""))
        comp = "below" if any(w in q for w in ("below", "under", "dip")) else "above"
        return {
            "event_type": "price_threshold",
            "market_type": "quant",
            "asset": "SOL",
            "threshold": threshold,
            "comparator": comp,
            "entities": ["SOL"],
            "tags": ["crypto", "threshold", "sol"],
        }

    # --- Price threshold: XRP ---
    xrp_match = re.search(r"(?:xrp|ripple).*?(?:above|below|over|under|reach|hit|dip)\s*(?:to\s*)?\$?([\d,]+(?:\.\d+)?)", q)
    if xrp_match:
        threshold = float(xrp_match.group(1).replace(",", ""))
        comp = "below" if any(w in q for w in ("below", "under", "dip")) else "above"
        return {
            "event_type": "price_threshold",
            "market_type": "quant",
            "asset": "XRP",
            "threshold": threshold,
            "comparator": comp,
            "entities": ["XRP"],
            "tags": ["crypto", "threshold", "xrp"],
        }

    # --- Price threshold: Generic crypto ---
    generic_match = re.search(r"(?:price of |will )([\w]+)\b.*?(?:above|below|over|under|reach|hit|dip)\s*(?:to\s*)?\$?([\d,]+(?:\.\d+)?)", q)
    if generic_match:
        token = generic_match.group(1).upper()
        if token in ("DOGE", "ADA", "BNB", "AVAX", "LINK", "UNI", "AAVE", "ARB", "OP", "SUI", "APT", "SEI", "NEAR", "MATIC"):
            threshold = float(generic_match.group(2).replace(",", ""))
            comp = "below" if any(w in q for w in ("below", "under", "dip")) else "above"
            return {
                "event_type": "price_threshold",
                "market_type": "quant",
                "asset": token,
                "threshold": threshold,
                "comparator": comp,
                "entities": [token],
                "tags": ["crypto", "threshold", token.lower()],
            }

    # --- ETF Catalyst ---
    if re.search(r"\betf\b", q):
        entities = _extract_entities(q)
        return {
            "event_type": "etf_catalyst",
            "market_type": "catalyst",
            "asset": _primary_asset(entities),
            "threshold": None,
            "comparator": None,
            "entities": entities,
            "tags": ["crypto", "etf", "catalyst"],
        }

    # --- Listing Catalyst ---
    if any(w in q for w in ("list on", "listing", "listed on", "list ")):
        has_exchange = any(e in q for e in ("binance", "coinbase", "kraken", "okx", "bybit"))
        if has_exchange or "listing" in q:
            entities = _extract_entities(q)
            return {
                "event_type": "listing_catalyst",
                "market_type": "catalyst",
                "asset": _primary_asset(entities),
                "threshold": None,
                "comparator": None,
                "entities": entities,
                "tags": ["crypto", "listing", "catalyst"],
            }

    # --- Token launch: "Will X launch a token?" ---
    if re.search(r"launch\s+(?:a\s+)?token", q):
        entities = _extract_entities(q)
        # Extract project name from "Will X launch a token"
        name_match = re.search(r"will\s+(\w+)\s+launch", q)
        if name_match and name_match.group(1) not in ("it", "they", "the"):
            proj = name_match.group(1).upper()
            if proj not in [e for e in entities]:
                entities.insert(0, proj)
        return {
            "event_type": "token_launch",
            "market_type": "catalyst",
            "asset": _primary_asset(entities) or (entities[0] if entities else None),
            "threshold": None,
            "comparator": None,
            "entities": entities,
            "tags": ["crypto", "token_launch", "catalyst"],
        }

    # --- Launch / Mainnet Catalyst ---
    if any(w in q for w in ("launch", "mainnet", "deploy")):
        entities = _extract_entities(q)
        return {
            "event_type": "launch_catalyst",
            "market_type": "catalyst",
            "asset": _primary_asset(entities),
            "threshold": None,
            "comparator": None,
            "entities": entities,
            "tags": ["crypto", "launch", "catalyst"],
        }

    # --- Crypto-related but unclassified: still route as generic_crypto ---
    crypto_kw = {"bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto",
                 "defi", "blockchain", "stablecoin", "nft", "usdt", "usdc", "tether",
                 "altcoin", "memecoin", "web3"}
    if any(re.search(r"\b" + re.escape(kw) + r"\b", q) for kw in crypto_kw):
        entities = _extract_entities(q)
        asset = _detect_asset_from_text(q) or _primary_asset(entities)
        return {
            "event_type": "generic_crypto",
            "market_type": "quant",
            "asset": asset,
            "threshold": None,
            "comparator": None,
            "entities": entities or ([asset] if asset else []),
            "tags": ["crypto", "generic"],
        }

    # --- Unknown ---
    return {
        "event_type": "unknown",
        "market_type": "unknown",
        "asset": None,
        "threshold": None,
        "comparator": None,
        "entities": _extract_entities(q),
        "tags": [],
    }


def _detect_asset_from_text(q: str) -> str | None:
    """Detect primary crypto asset from text using ASSET_MAP."""
    for token, asset in ASSET_MAP.items():
        if re.search(r"\b" + re.escape(token) + r"\b", q):
            return asset
    return None


def _extract_entities(q: str) -> list[str]:
    """Extract known entities from question text using word boundaries."""
    found = []
    for token in KNOWN_ENTITIES:
        if re.search(r"\b" + re.escape(token) + r"\b", q):
            found.append(token.upper())
    return list(dict.fromkeys(found))  # dedup preserving order


def _primary_asset(entities: list[str]) -> str | None:
    """Get the primary crypto asset from entities."""
    for e in entities:
        if e in ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "AVAX", "LINK", "UNI"):
            return e
    return entities[0] if entities else None
