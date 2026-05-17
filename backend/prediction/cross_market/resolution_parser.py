"""
Resolution Parser — extracts structured resolution primitives from market questions.

Primitives:
  PRICE_THRESHOLD  — "BTC above $70k" → entity=BTC, threshold=70000, direction=ABOVE
  PRICE_RANGE      — "BTC between $60k-$65k"
  FDV_THRESHOLD    — "FDV above $1B"
  UP_DOWN          — "BTC up or down"
  INTENT           — "announce intention"
  SIGNED_DEAL      — "acquisition signed"
  APPROVAL         — "SEC approves"
  LISTING          — "token listed"
"""
import re
import logging

logger = logging.getLogger("cross_market.resolution_parser")

# Keyword → primitive mapping
KEYWORD_PRIMITIVES = [
    (r"above\s+\$", "PRICE_THRESHOLD"),
    (r"reach\s+\$", "PRICE_THRESHOLD"),
    (r"between\s+\$.*and\s+\$", "PRICE_RANGE"),
    (r"less\s+than\s+\$", "PRICE_THRESHOLD"),
    (r"fdv\s+above", "FDV_THRESHOLD"),
    (r"up\s+or\s+down", "UP_DOWN"),
    (r"announce.*intention", "INTENT"),
    (r"acquisition.*sign", "SIGNED_DEAL"),
    (r"sec\s+approv", "APPROVAL"),
    (r"etf\s+approv", "APPROVAL"),
    (r"list(?:ed|ing)\s+on", "LISTING"),
    (r"launch", "LISTING"),
    (r"convicted", "LEGAL_OUTCOME"),
    (r"committed", "COMMITMENT_THRESHOLD"),
]


def parse_resolution(market: dict) -> dict:
    """Parse a market question into resolution primitives."""
    question = market.get("question", "")
    q_lower = question.lower()

    primitive = "UNKNOWN"
    for pattern, prim in KEYWORD_PRIMITIVES:
        if re.search(pattern, q_lower):
            primitive = prim
            break

    threshold = market.get("threshold", 0)
    direction = "ABOVE"
    if "less than" in q_lower or "below" in q_lower:
        direction = "BELOW"
    if "between" in q_lower:
        direction = "BETWEEN"

    return {
        "market_id": market.get("market_id", ""),
        "question": question,
        "primitive": primitive,
        "threshold": threshold,
        "direction": direction,
        "yes_price": market.get("yes_price"),
        "confidence": _parser_confidence(primitive, threshold),
        "volume": market.get("volume", 0),
        "spread": market.get("spread"),
    }


def _parser_confidence(primitive: str, threshold: float) -> float:
    """How confident we are in the parse result."""
    if primitive == "UNKNOWN":
        return 0.1
    if primitive in ("PRICE_THRESHOLD", "FDV_THRESHOLD") and threshold > 0:
        return 0.95
    if primitive == "PRICE_RANGE":
        return 0.85
    if primitive in ("INTENT", "SIGNED_DEAL", "APPROVAL"):
        return 0.80
    return 0.70


def parse_cluster_resolutions(topic: dict) -> dict:
    """Parse all markets in a topic cluster."""
    markets = topic.get("markets", [])
    parsed = [parse_resolution(m) for m in markets]

    # Determine if this is a consistent ladder
    primitives = set(p["primitive"] for p in parsed)
    is_ladder = (
        len(primitives) == 1
        and list(primitives)[0] in ("PRICE_THRESHOLD", "FDV_THRESHOLD")
        and len(parsed) >= 3
    )

    return {
        "topic_key": topic["topic_key"],
        "entity": topic["entity"],
        "time_frame": topic["time_frame"],
        "topic_type": topic["topic_type"],
        "is_ladder": is_ladder,
        "primitives": sorted(primitives),
        "parsed_markets": parsed,
        "market_count": len(parsed),
    }
