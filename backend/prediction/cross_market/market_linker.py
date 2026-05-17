"""
Market Linker — groups related markets into clusters.

Links markets by:
  1. Same entity (BTC, ETH, SOL, etc.)
  2. Same topic type (price_target, price_range, fdv, direction)
  3. Same time frame (March, April, Q1, etc.)

Output: list of MarketCluster dicts.
"""
import re
import logging
from collections import defaultdict

logger = logging.getLogger("cross_market.market_linker")

# Entity extraction patterns
ENTITY_PATTERNS = {
    "BTC": r"\b(?:bitcoin|btc)\b",
    "ETH": r"\b(?:ethereum|eth|ether)\b",
    "SOL": r"\b(?:solana|sol)\b",
    "XRP": r"\b(?:xrp|ripple)\b",
    "BNB": r"\b(?:bnb|binance)\b",
    "DOGE": r"\b(?:doge|dogecoin)\b",
    "ADA": r"\b(?:ada|cardano)\b",
    "AVAX": r"\b(?:avax|avalanche)\b",
    "LINK": r"\b(?:link|chainlink)\b",
    "DOT": r"\b(?:dot|polkadot)\b",
}

# Time frame patterns
TIME_PATTERNS = [
    (r"\b(?:january|jan)\b", "january"),
    (r"\b(?:february|feb)\b", "february"),
    (r"\b(?:march|mar)\b", "march"),
    (r"\b(?:april|apr)\b", "april"),
    (r"\b(?:may)\b", "may"),
    (r"\b(?:june|jun)\b", "june"),
    (r"\b(?:q1)\b", "q1"),
    (r"\b(?:q2)\b", "q2"),
    (r"\b(?:2026)\b", "2026"),
    (r"\b(?:2027)\b", "2027"),
]


def extract_entities(text: str) -> list[str]:
    """Extract known crypto entities from text."""
    text_lower = text.lower()
    found = []
    for entity, pattern in ENTITY_PATTERNS.items():
        if re.search(pattern, text_lower):
            found.append(entity)
    return found


def extract_time_frame(text: str) -> str:
    """Extract time frame from text."""
    text_lower = text.lower()
    # Try specific date first
    date_match = re.search(r"(?:on|by)\s+((?:march|april|may|june|january|february)\s+\d{1,2})", text_lower)
    if date_match:
        return date_match.group(1).replace(" ", "_")
    # Try month
    for pattern, label in TIME_PATTERNS:
        if re.search(pattern, text_lower):
            return label
    return "unknown"


def extract_threshold(text: str) -> float:
    """Extract numeric threshold from market question."""
    # Match dollar amounts: $70,000 or $70k or $1B etc
    m = re.search(r"\$([0-9,]+(?:\.\d+)?)\s*([kmbt])?", text.lower().replace(",", ""))
    if m:
        val = float(m.group(1))
        suffix = m.group(2)
        if suffix == "k":
            val *= 1_000
        elif suffix == "m":
            val *= 1_000_000
        elif suffix == "b":
            val *= 1_000_000_000
        elif suffix == "t":
            val *= 1_000_000_000_000
        return val
    # Match plain numbers
    m = re.search(r"(?:above|below|reach|hit)\s+\$?([0-9,]+)", text.lower().replace(",", ""))
    if m:
        return float(m.group(1))
    return 0


def link_markets(events: list[dict]) -> list[dict]:
    """Link events into market clusters."""
    clusters = defaultdict(lambda: {
        "markets": [],
        "entities": set(),
        "topic_types": set(),
        "time_frames": set(),
    })

    for event in events:
        title = event.get("title", "")
        asset_group = event.get("asset_group", "")
        event_type = event.get("event_type", "")
        entities = extract_entities(title)
        if not entities and asset_group:
            entities = [asset_group.upper()]
        time_frame = extract_time_frame(title)

        # Build cluster key: entity + topic_type + time_frame
        for entity in entities:
            cluster_key = f"{entity}:{event_type}:{time_frame}"
            c = clusters[cluster_key]
            c["entities"].add(entity)
            c["topic_types"].add(event_type)
            c["time_frames"].add(time_frame)

            # Add individual markets from this event
            for mkt in event.get("markets", []):
                question = mkt.get("question", "")
                threshold = extract_threshold(question)
                c["markets"].append({
                    "market_id": mkt.get("id", ""),
                    "event_id": event.get("event_id", ""),
                    "question": question,
                    "yes_price": mkt.get("yes_price"),
                    "threshold": threshold,
                    "asset_group": asset_group,
                    "event_type": event_type,
                    "title": title,
                    "volume": mkt.get("volume", 0),
                    "best_bid": mkt.get("best_bid"),
                    "best_ask": mkt.get("best_ask"),
                    "spread": mkt.get("spread") or mkt.get("live_spread"),
                })

    # Convert to output format, only clusters with 2+ markets
    result = []
    for cluster_key, data in clusters.items():
        if len(data["markets"]) < 2:
            continue
        result.append({
            "cluster_key": cluster_key,
            "entities": sorted(data["entities"]),
            "topic_types": sorted(data["topic_types"]),
            "time_frames": sorted(data["time_frames"]),
            "market_count": len(data["markets"]),
            "markets": sorted(data["markets"], key=lambda m: m.get("threshold", 0)),
        })

    logger.info(f"[MarketLinker] {len(events)} events → {len(result)} clusters")
    return result
