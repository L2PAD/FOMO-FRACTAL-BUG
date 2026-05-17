"""
Polymarket Client — fetches and normalizes markets from Gamma API.

Fetches live (non-closed) markets, filters out resolved/degenerate prices,
and prioritises crypto-relevant markets for the Decision Desk.
"""
import httpx
import json
import logging

logger = logging.getLogger("prediction.polymarket")

GAMMA_API = "https://gamma-api.polymarket.com"

import re as _re

# Short tokens that need word-boundary matching to avoid false positives
_SHORT_TOKENS = {"btc", "eth", "sol", "xrp", "ada", "bnb", "op", "sui", "apt", "sei", "uni", "arb", "nft", "etf", "token"}

CRYPTO_KEYWORDS = {
    "bitcoin", "ethereum", "solana", "ripple",
    "doge", "dogecoin", "cardano", "avax", "matic", "polygon",
    "chainlink", "uniswap", "aave", "arbitrum",
    "optimism", "aptos", "near", "crypto",
    "coinbase", "binance", "blockchain", "defi",
    "stablecoin", "usdt", "usdc", "tether",
}

# Pre-compiled regex for short tokens: \b(btc|eth|sol|...)\b
_SHORT_PATTERN = _re.compile(r"\b(" + "|".join(_SHORT_TOKENS) + r")\b", _re.IGNORECASE)


async def fetch_markets(limit: int = 50) -> list[dict]:
    """
    Fetch live crypto-relevant markets from Polymarket.
    Filters out resolved markets (price near 0 or 1) and non-crypto noise.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Fetch a larger pool, then filter for crypto + live prices
            fetch_size = max(limit * 4, 200)
            resp = await client.get(f"{GAMMA_API}/markets", params={
                "limit": fetch_size,
                "closed": False,
                "order": "volume",
                "ascending": False,
            })
            if resp.status_code != 200:
                logger.warning(f"Polymarket API returned {resp.status_code}")
                return []
            raw_markets = resp.json()
            if not isinstance(raw_markets, list):
                return []

            results = []
            for m in raw_markets:
                if not m.get("question"):
                    continue
                norm = _normalize(m)
                if not _is_live(norm):
                    continue
                if _is_crypto_relevant(norm):
                    results.append(norm)
                if len(results) >= limit:
                    break

            return results
    except Exception as e:
        logger.error(f"Polymarket fetch error: {e}")
        return []


def _is_live(m: dict) -> bool:
    """Filter out resolved/degenerate markets."""
    yp = m["yes_price"]
    return 0.02 < yp < 0.98 and m["liquidity"] > 0


def _is_crypto_relevant(m: dict) -> bool:
    """Check if market is related to crypto/blockchain."""
    q = m["question"].lower()
    # Long keywords: simple substring match
    if any(kw in q for kw in CRYPTO_KEYWORDS):
        return True
    # Short tokens: word-boundary match to avoid false positives
    if _SHORT_PATTERN.search(q):
        return True
    return False


def _normalize(raw: dict) -> dict:
    """Normalize a raw Polymarket market into a clean dict."""
    outcomes = raw.get("outcomePrices", "")
    yes_price = 0.0
    no_price = 0.0

    if isinstance(outcomes, str) and outcomes:
        try:
            prices = json.loads(outcomes)
            if isinstance(prices, list) and len(prices) >= 2:
                yes_price = float(prices[0])
                no_price = float(prices[1])
        except Exception:
            pass
    elif isinstance(outcomes, list) and len(outcomes) >= 2:
        yes_price = float(outcomes[0])
        no_price = float(outcomes[1])

    volume = float(raw.get("volume", 0) or 0)
    liquidity = float(raw.get("liquidityClob", 0) or raw.get("liquidity", 0) or 0)

    # CLOB token IDs for orderbook queries
    clob_ids_raw = raw.get("clobTokenIds", [])
    if isinstance(clob_ids_raw, str):
        try:
            clob_ids_raw = json.loads(clob_ids_raw)
        except Exception:
            clob_ids_raw = []
    yes_token = clob_ids_raw[0] if len(clob_ids_raw) > 0 else None
    no_token = clob_ids_raw[1] if len(clob_ids_raw) > 1 else None

    # Best bid/ask from Gamma (CLOB-sourced, more accurate than computed spread)
    best_bid = float(raw.get("bestBid", 0) or 0)
    best_ask = float(raw.get("bestAsk", 0) or 0)

    return {
        "market_id": raw.get("id", ""),
        "question": raw.get("question", ""),
        "category": raw.get("category", ""),
        "yes_price": yes_price,
        "no_price": no_price,
        "volume": volume,
        "liquidity": liquidity,
        "spread": abs(yes_price - no_price) if yes_price and no_price else 0,
        "end_date": raw.get("endDate"),
        "raw_rules": raw.get("description", ""),
        "yes_token_id": yes_token,
        "no_token_id": no_token,
        "best_bid": best_bid,
        "best_ask": best_ask,
    }
