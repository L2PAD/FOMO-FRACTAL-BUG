"""
Resolution Parser v2 — extracts structured resolution primitives from market text.

Returns an array of primitives (not just one type) with strictness scoring.

Primitives:
  PRICE_THRESHOLD, RANGE, UP_DOWN,
  INTENT_ANNOUNCED, FORMAL_PROCESS,
  SIGNED_DEAL, BUYER_NAMED, CONTROL_TRANSFER,
  APPROVAL, LISTING
"""
import re
import logging

logger = logging.getLogger("cross_market.kalshi.resolution_parser_v2")

PRIMITIVES_MAP = {
    "PRICE_THRESHOLD": [
        "above", "below", "exceed", "greater than", "less than",
        "reaches", "hits", "surpass", "at or above",
    ],
    "RANGE": [
        "between", "price range", "within range",
    ],
    "INTENT_ANNOUNCED": [
        "announce", "intends to", "plans to", "intention",
        "considering", "exploring",
    ],
    "FORMAL_PROCESS": [
        "formal process", "regulatory", "review", "filing",
    ],
    "SIGNED_DEAL": [
        "signed deal", "agreement signed", "definitive agreement",
        "binding agreement", "executed agreement",
    ],
    "BUYER_NAMED": [
        "buyer named", "identified buyer", "acquirer named",
        "purchasing entity",
    ],
    "CONTROL_TRANSFER": [
        "control transfer", "ownership transferred", "change of control",
        "divested", "sold to",
    ],
    "APPROVAL": [
        "approved", "approval granted", "regulatory approval",
        "fda approval", "sec approval",
    ],
    "LISTING": [
        "listed on", "ipo", "initial public offering", "listed",
    ],
}

# Strictness weight per primitive
STRICTNESS_WEIGHTS = {
    "PRICE_THRESHOLD": 0.1,
    "RANGE": 0.1,
    "UP_DOWN": 0.1,
    "INTENT_ANNOUNCED": 0.2,
    "FORMAL_PROCESS": 0.3,
    "SIGNED_DEAL": 0.4,
    "BUYER_NAMED": 0.2,
    "CONTROL_TRANSFER": 0.2,
    "APPROVAL": 0.3,
    "LISTING": 0.2,
}


def extract_primitives(text: str) -> list[str]:
    """Extract all matching resolution primitives from text."""
    text_lower = text.lower()
    primitives = []

    for prim_type, keywords in PRIMITIVES_MAP.items():
        if any(kw in text_lower for kw in keywords):
            primitives.append(prim_type)

    return primitives


def detect_threshold(text: str) -> tuple[float, str | None]:
    """Extract numeric threshold and direction from text."""
    text_lower = text.lower()

    # "above X" or "above X.XX"
    above = re.search(r'above\s+\$?(\d[\d,]*\.?\d*)', text_lower)
    if above:
        val = float(above.group(1).replace(",", ""))
        return val, "ABOVE"

    # "below X"
    below = re.search(r'below\s+\$?(\d[\d,]*\.?\d*)', text_lower)
    if below:
        val = float(below.group(1).replace(",", ""))
        return val, "BELOW"

    # "between X-Y" or "between X and Y"
    between = re.search(r'between\s+\$?(\d[\d,]*\.?\d*)', text_lower)
    if between:
        val = float(between.group(1).replace(",", ""))
        return val, "BETWEEN"

    # "greater than X"
    gt = re.search(r'greater\s+than\s+\$?(\d[\d,]*\.?\d*)', text_lower)
    if gt:
        val = float(gt.group(1).replace(",", ""))
        return val, "ABOVE"

    # Generic numeric extraction (last resort)
    nums = re.findall(r'\$(\d[\d,]*\.?\d*)', text_lower)
    if nums:
        val = float(nums[0].replace(",", ""))
        return val, None

    return 0, None


def detect_time_bucket(text: str) -> str | None:
    """Detect time bucket from text."""
    text_lower = text.lower()

    if any(x in text_lower for x in ["tomorrow", "next day", "24 hours"]):
        return "INTRADAY"
    if any(x in text_lower for x in ["this week", "by friday", "end of week"]):
        return "SHORT_TERM"
    if any(x in text_lower for x in ["this month", "end of month", "by end of"]):
        return "MONTHLY"
    if any(x in text_lower for x in ["this year", "by year end", "end of year"]):
        return "YEARLY"
    if any(x in text_lower for x in ["2026", "2027", "2028"]):
        return "YEARLY"

    # Detect specific month references
    months = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december",
              "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if any(m in text_lower for m in months):
        return "MONTHLY"

    return None


def compute_strictness(primitives: list[str]) -> float:
    """Compute how strict/demanding the resolution condition is."""
    score = 0.0
    for p in primitives:
        score += STRICTNESS_WEIGHTS.get(p, 0.1)
    return min(score, 1.0)


def compute_confidence(text: str, primitives: list[str]) -> float:
    """How confident we are in the parse."""
    if not primitives:
        return 0.3
    if len(primitives) >= 2:
        return 0.85
    if "PRICE_THRESHOLD" in primitives:
        return 0.90  # Very clear parsing
    return 0.65


def parse_resolution_v2(market: dict) -> dict:
    """Parse a market into structured resolution primitives.

    Works with both Polymarket and Kalshi market dicts.
    """
    question = market.get("question", "") or ""
    rules = market.get("rules", "") or market.get("rules_primary", "") or ""
    text = f"{question} {rules}"

    primitives = extract_primitives(text)
    threshold, direction = detect_threshold(text)
    time_bucket = detect_time_bucket(text)
    strictness = compute_strictness(primitives)
    confidence = compute_confidence(text, primitives)

    market_id = market.get("id", "") or market.get("market_id", "")
    platform = market.get("platform", "polymarket")

    return {
        "market_id": market_id,
        "platform": platform,
        "primitives": primitives,
        "threshold": threshold,
        "direction": direction,
        "time_bucket": time_bucket,
        "strictness_score": strictness,
        "parser_confidence": confidence,
        "question": question[:200],
        "rules_snippet": rules[:200],
    }
