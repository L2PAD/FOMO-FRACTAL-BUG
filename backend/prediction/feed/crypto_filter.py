"""
Crypto Event Filter — 3-layer filtering for crypto relevance.

Layer 1: Keyword filter (phrase + word-boundary exact match)
Layer 2: Entity validation (verify known crypto entity present)
Layer 3: Context classifier (reject political, generic news, non-crypto)

Filters by title/slug/tags/question keywords.
Short tickers (btc, eth, sol) use word-boundary regex to avoid false positives
(e.g. "Netherlands" matching "eth").

Also classifies asset group (BTC, ETH, SOL, XRP, ALT) and category.
"""
import re

# ── Layer 1: Keyword matching ──

CRYPTO_PHRASE_KEYWORDS = [
    "bitcoin", "ethereum", "solana", "ripple", "crypto", "cryptocurrency",
    "blockchain", "defi", "doge", "dogecoin", "cardano",
    "matic", "polygon", "arbitrum", "aptos", "stablecoin", "usdc", "usdt",
    "tether", "altcoin", "memecoin", "meme coin", "coinbase", "binance",
    "kraken", "uniswap", "aave", "pengu", "initia", "kaito", "walrus",
    "berachain", "megaeth", "loopscale", "edgex", "hyperliquid",
    "monad", "zksync", "starknet", "celestia", "mantle",
    "token launch", "token price", "airdrop",
    "fully diluted",
]

CRYPTO_EXACT_WORDS = {"btc", "eth", "sol", "xrp", "bnb", "ada", "apt", "sei", "fdv", "nft", "sui", "mcap", "avax"}

_exact_pattern = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in CRYPTO_EXACT_WORDS) + r')\b',
    re.IGNORECASE,
)

# ── Layer 2: Known crypto entities ──

KNOWN_CRYPTO_ENTITIES = {
    "bitcoin", "ethereum", "solana", "ripple", "xrp", "dogecoin", "doge",
    "cardano", "polygon", "arbitrum", "aptos", "avalanche", "celestia",
    "mantle", "starknet", "zksync", "monad", "berachain", "megaeth",
    "hyperliquid", "uniswap", "aave", "pengu", "initia", "kaito",
    "walrus", "loopscale", "edgex", "coinbase", "binance", "kraken",
    "btc", "eth", "sol", "bnb", "ada", "apt", "sei", "sui", "avax",
    "based", "worldcoin", "wld", "pepe", "shiba", "bonk",
}

# ── Layer 3: Negative context (political / generic / non-crypto) ──

POLITICAL_KEYWORDS = [
    "president", "election", "congress", "senate", "democrat", "republican",
    "trump", "biden", "vance", "pelosi", "governor", "parliament",
    "impeach", "indictment", "vote", "ballot", "primary",
    "immigration", "border wall", "abortion", "gun control",
]

NON_CRYPTO_KEYWORDS = [
    "spacex", "ipo", "nfl", "nba", "mlb", "nhl", "super bowl",
    "oscars", "grammys", "emmy", "world cup", "olympics",
    "war ", "invasion", "nuclear", "nato", "united nations",
    "earthquake", "hurricane", "wildfire",
    "tv show", "movie", "celebrity", "dating",
]

# Words that if present alongside a crypto keyword, still mark event as non-crypto
CONTEXT_NEGATORS = [
    "iran", "north korea", "syria", "ukraine", "russia",
    "assassination", "coup", "hostage", "terror",
]


def is_crypto_event(event: dict) -> bool:
    """3-layer crypto relevance check."""
    combined = _build_combined_text(event)
    title = (event.get("title", "") or "").lower()

    # Layer 1: Must match at least one crypto keyword
    has_phrase = any(kw in combined for kw in CRYPTO_PHRASE_KEYWORDS)
    has_exact = bool(_exact_pattern.search(combined))

    if not has_phrase and not has_exact:
        return False

    # Layer 2: Entity validation — check for known crypto entity
    has_entity = any(e in combined for e in KNOWN_CRYPTO_ENTITIES)

    # Layer 3: Context classifier — reject non-crypto contexts
    has_political = any(kw in combined for kw in POLITICAL_KEYWORDS)
    has_non_crypto = any(kw in combined for kw in NON_CRYPTO_KEYWORDS)
    has_negator = any(kw in combined for kw in CONTEXT_NEGATORS)

    # If strong political context + weak crypto signal, reject
    if has_political and not has_entity:
        return False

    # If non-crypto context dominates, reject
    if has_non_crypto and not has_entity:
        return False

    # If context negator present and crypto signal is only from tags, reject
    if has_negator and not _title_has_crypto(title):
        return False

    return True


ASSET_GROUPS = {
    "BTC": ["bitcoin", "btc", "microstrategy"],
    "ETH": ["ethereum", "eth"],
    "SOL": ["solana", "sol"],
    "XRP": ["xrp", "ripple"],
}


def _title_has_crypto(title: str) -> bool:
    """Check if the event TITLE itself (not tags) contains crypto keywords."""
    if any(kw in title for kw in CRYPTO_PHRASE_KEYWORDS):
        return True
    if _exact_pattern.search(title):
        return True
    return False


def detect_asset_group(event: dict) -> str:
    """Detect primary asset: BTC, ETH, SOL, XRP, or ALT."""
    title = (event.get("title", "") or "").lower()
    slug = (event.get("slug", "") or "").lower()
    combined = f"{title} {slug}"

    for asset, keywords in ASSET_GROUPS.items():
        for kw in keywords:
            if len(kw) <= 3:
                if re.search(r'\b' + re.escape(kw) + r'\b', combined, re.IGNORECASE):
                    return asset
            else:
                if kw in combined:
                    return asset
    return "ALT"


def detect_category(event: dict) -> str:
    """Detect market category: fdv, launch, etf, macro, price, direction."""
    title = (event.get("title", "") or "").lower()
    slug = (event.get("slug", "") or "").lower()
    combined = f"{title} {slug}"

    if "fdv" in combined or "fully diluted" in combined or "market cap" in combined:
        return "fdv"
    if "launch" in combined or "airdrop" in combined or "listing" in combined:
        return "launch"
    if "etf" in combined:
        return "etf"
    if any(kw in combined for kw in ["tax", "regulation", "ban", "fed ", "tariff"]):
        return "macro"
    if "up or down" in combined:
        return "direction"
    if re.search(r"(above|below|hit|reach|price)", combined):
        return "price"
    return "other"


def _build_combined_text(event: dict) -> str:
    """Build combined searchable text from event."""
    title = (event.get("title", "") or "").lower()
    slug = (event.get("slug", "") or "").lower()

    tags = event.get("tags", [])
    tag_str = ""
    for t in tags:
        if isinstance(t, dict):
            tag_str += " " + (t.get("label", "") or t.get("slug", "")).lower()
        elif isinstance(t, str):
            tag_str += " " + t.lower()

    markets = event.get("markets", [])
    questions = " ".join((m.get("question", "") or "").lower() for m in markets[:5])

    return f"{title} {slug} {tag_str} {questions}"
