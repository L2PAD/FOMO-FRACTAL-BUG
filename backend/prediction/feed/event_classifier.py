"""
Event Classifier — classifies event/market type.

Types:
  - direction: "Bitcoin Up or Down"
  - price_target: "Bitcoin above $70k on March 31?"
  - price_range: "What price will Bitcoin hit in March?"
  - fdv: "MegaETH FDV above $X?"
  - launch: "Will X launch a token by?"
  - etf: "Will X ETF be approved?"
  - macro: "Trump eliminates capital gains tax on crypto?"
  - other: unclassified
"""
import re


def classify_event(event: dict) -> str:
    """Classify event into market type category."""
    title = (event.get("title", "") or "").lower()
    slug = (event.get("slug", "") or "").lower()
    combined = f"{title} {slug}"

    if "up or down" in combined:
        return "direction"
    if "fdv" in combined or "market cap" in combined:
        return "fdv"
    if re.search(r"what price will .+ hit", combined):
        return "price_range"
    if re.search(r"(above|below|reach|hit \$)", combined):
        return "price_target"
    if "launch" in combined or "airdrop" in combined:
        return "launch"
    if "etf" in combined:
        return "etf"
    if any(kw in combined for kw in ["tax", "regulation", "ban", "fed ", "tariff"]):
        return "macro"
    if "listing" in combined:
        return "launch"
    return "other"


def extract_threshold_from_question(question: str) -> float | None:
    """Extract price threshold from question like 'Bitcoin above $70,000'."""
    q = question.lower().replace(",", "").replace("$", "")
    # Match patterns like "above 70000", "hit 2100", "reach 150k"
    m = re.search(r"(?:above|below|hit|reach|at)\s+(\d+(?:\.\d+)?)\s*(k)?", q)
    if m:
        val = float(m.group(1))
        if m.group(2):
            val *= 1000
        return val
    return None


def is_binary_event(event: dict) -> bool:
    """Check if event is simple binary (1 market, YES/NO)."""
    markets = event.get("markets", [])
    return len(markets) == 1


def is_multi_outcome(event: dict) -> bool:
    """Check if event has multiple outcome markets."""
    markets = event.get("markets", [])
    return len(markets) > 1
