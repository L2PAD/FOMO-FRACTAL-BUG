"""
Resolution Engine — analyzes market rules for clarity and risk.

Determines whether a market is safe to trade based on:
  - rule presence and quality
  - time boundary clarity
  - resolution source explicitness
  - wording ambiguity
  - binary outcome clarity

Output:
  - rule_clarity_score (0-1)
  - resolution_risk_score (0-1)
  - tradable (bool)
  - flags (list of risk descriptions)
"""
import re


# Penalty weights for each flag type
FLAG_PENALTIES = {
    "missing_rules": 0.25,
    "time_ambiguous": 0.12,
    "deadline_boundary_risk": 0.10,
    "resolution_source_missing": 0.15,
    "source_unclear": 0.08,
    "binary_outcome_unclear": 0.12,
    "wording_conflict": 0.10,
    "clarification_present": -0.05,  # positive: clarification reduces risk
}

# Keywords that indicate clear resolution sources
CLEAR_SOURCE_KEYWORDS = [
    "according to", "as reported by", "official", "coinmarketcap",
    "coingecko", "binance", "coinbase", "tradingview", "bloomberg",
    "reuters", "sec.gov", "federal register",
]

# Keywords that indicate time ambiguity
TIME_AMBIGUOUS_PATTERNS = [
    r"\bby\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    r"\bby\s+q[1-4]\b",
    r"\bby\s+(end\s+of\s+)?(the\s+)?(year|month|quarter)\b",
    r"\bthis\s+(year|month|quarter)\b",
]

# Keywords that indicate clear time boundaries
TIME_CLEAR_PATTERNS = [
    r"\d{1,2}:\d{2}\s*(am|pm|et|utc|gmt)",
    r"\d{4}-\d{2}-\d{2}",
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}",
]


def analyze(question: str, rules: str | None) -> dict:
    """
    Analyze market question and rules for resolution risks.

    Returns:
        dict with rule_clarity_score, resolution_risk_score, tradable, flags
    """
    q = (question or "").lower()
    r = (rules or "").lower()
    combined = q + " " + r

    flags = []
    penalty = 0.0

    # --- Missing rules ---
    if not rules or len(rules.strip()) < 20:
        flags.append("missing_rules")
        penalty += FLAG_PENALTIES["missing_rules"]

    # --- Time ambiguity ---
    has_clear_time = any(re.search(p, combined) for p in TIME_CLEAR_PATTERNS)
    has_ambiguous_time = any(re.search(p, combined) for p in TIME_AMBIGUOUS_PATTERNS)

    if has_ambiguous_time and not has_clear_time:
        flags.append("time_ambiguous")
        penalty += FLAG_PENALTIES["time_ambiguous"]

    # --- Deadline boundary risk ---
    if any(w in combined for w in ["before", "by end of", "on or before"]):
        if not has_clear_time:
            flags.append("deadline_boundary_risk")
            penalty += FLAG_PENALTIES["deadline_boundary_risk"]

    # --- Resolution source ---
    has_clear_source = any(kw in combined for kw in CLEAR_SOURCE_KEYWORDS)
    if not has_clear_source:
        flags.append("resolution_source_missing")
        penalty += FLAG_PENALTIES["resolution_source_missing"]
    if rules and not any(kw in r for kw in CLEAR_SOURCE_KEYWORDS):
        if "resolution_source_missing" not in flags:
            flags.append("source_unclear")
            penalty += FLAG_PENALTIES["source_unclear"]

    # --- Binary outcome clarity ---
    ambiguous_words = ["might", "could", "possibly", "approximately", "around", "roughly"]
    if any(w in q for w in ambiguous_words):
        flags.append("binary_outcome_unclear")
        penalty += FLAG_PENALTIES["binary_outcome_unclear"]

    # --- Wording conflict (question vs rules mismatch) ---
    if rules and len(rules) > 50:
        q_numbers = set(re.findall(r'\d{4,}', q))
        r_numbers = set(re.findall(r'\d{4,}', r))
        if q_numbers and r_numbers and q_numbers != r_numbers:
            flags.append("wording_conflict")
            penalty += FLAG_PENALTIES["wording_conflict"]

    # --- Clarification present (reduces risk) ---
    if rules and any(w in r for w in ["clarification", "updated", "amendment", "note:"]):
        flags.append("clarification_present")
        penalty += FLAG_PENALTIES["clarification_present"]

    rule_clarity = max(0.0, min(1.0, 1.0 - penalty))
    resolution_risk = max(0.0, min(1.0, penalty))

    # Tradable: false if too risky
    tradable = resolution_risk < 0.35

    return {
        "rule_clarity_score": round(rule_clarity, 4),
        "resolution_risk_score": round(resolution_risk, 4),
        "tradable": tradable,
        "flags": [f for f in flags if f != "clarification_present"],
        "has_clarification": "clarification_present" in flags,
    }
