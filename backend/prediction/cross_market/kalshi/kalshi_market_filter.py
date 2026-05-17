"""
Kalshi Market Filter — filters markets for relevance and quality.

Only keeps:
  - Crypto-related markets (entity validation)
  - Markets with meaningful data (price, volume)
  - ABOVE direction preferred for cross-platform comparison
"""
import logging

logger = logging.getLogger("cross_market.kalshi.filter")

# Entity allowlist for crypto
VALID_ENTITIES = {"BTC", "ETH", "SOL"}

# Minimum quality thresholds
MIN_YES_PRICE = 0.001  # Must have some price
MIN_LIQUIDITY_OR_VOLUME = 0  # Accept even zero for now (Kalshi crypto is thin)


def is_crypto_market(market: dict) -> bool:
    """Check if market is crypto-related via entity + context validation."""
    entity = market.get("entity", "")
    if entity in VALID_ENTITIES:
        return True

    # Fallback: check rules and title for crypto keywords
    rules = (market.get("rules", "") or "").lower()
    question = (market.get("question", "") or "").lower()
    combined = rules + " " + question

    crypto_indicators = [
        "bitcoin", "btc", "ethereum", "eth",
        "cf benchmarks", "brti", "erti",
        "crypto", "solana",
    ]
    return any(ind in combined for ind in crypto_indicators)


def is_quality_market(market: dict) -> bool:
    """Check basic quality: has price data."""
    yes_price = market.get("yes_price", 0) or 0
    return yes_price >= MIN_YES_PRICE


def is_useful_for_comparison(market: dict) -> bool:
    """Check if market is useful for cross-platform comparison.

    Prefer ABOVE direction (matches Polymarket ladder structure).
    BETWEEN markets are less useful for 1:1 matching.
    """
    direction = market.get("direction")
    # Accept ABOVE and BELOW, skip BETWEEN (too granular)
    if direction == "BETWEEN":
        return False
    return True


def filter_markets(markets: list[dict]) -> list[dict]:
    """Apply all filters to normalized Kalshi markets.

    Returns only crypto + quality + useful markets.
    """
    filtered = []
    skipped_entity = 0
    skipped_quality = 0
    skipped_comparison = 0

    for m in markets:
        if not is_crypto_market(m):
            skipped_entity += 1
            continue
        if not is_quality_market(m):
            skipped_quality += 1
            continue
        if not is_useful_for_comparison(m):
            skipped_comparison += 1
            continue
        filtered.append(m)

    logger.info(
        f"[KalshiFilter] {len(markets)} → {len(filtered)} "
        f"(skipped: entity={skipped_entity}, quality={skipped_quality}, "
        f"comparison={skipped_comparison})"
    )
    return filtered
