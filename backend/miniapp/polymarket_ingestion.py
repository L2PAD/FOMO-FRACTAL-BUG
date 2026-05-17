"""
Polymarket Ingestion — Real market data pipeline
=================================================
Fetches live crypto markets from Polymarket, maps them to assets,
extracts price thresholds, and stores in prediction_markets collection.
Then Edge Engine uses real market probabilities.
"""

import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("miniapp.polymarket_ingestion")

# Asset mapping patterns
ASSET_PATTERNS = [
    (r"\bbitcoin\b|\bbtc\b", "BTC"),
    (r"\bethereum\b|\beth\b", "ETH"),
    (r"\bsolana\b|\bsol\b", "SOL"),
    (r"\bxrp\b|\bripple\b", "XRP"),
    (r"\bdogecoin\b|\bdoge\b", "DOGE"),
    (r"\bcardano\b|\bada\b", "ADA"),
    (r"\bavax\b|\bavalanche\b", "AVAX"),
    (r"\bbnb\b|\bbinance\b", "BNB"),
]

# Price threshold extraction patterns
PRICE_PATTERNS = [
    # "$70,000" or "$70k" or "$70K"
    re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*[kK]", re.IGNORECASE),
    re.compile(r"\$\s*([\d,]+(?:\.\d+)?)"),
    # "70000" or "70k" without $
    re.compile(r"\b(\d{2,6})[kK]\b"),
]

# Direction patterns
ABOVE_PATTERNS = re.compile(r"above|over|exceed|reach|hit|surpass|higher than|at least|more than|\bup\b", re.IGNORECASE)
BELOW_PATTERNS = re.compile(r"below|under|drop|fall|less than|lower than|\bdown\b", re.IGNORECASE)

# Whitelist assets for Edge Engine
EDGE_ASSETS = {"BTC", "ETH", "SOL"}


def _detect_asset(question: str) -> str:
    """Map a market question to an asset ticker."""
    q = question.lower()
    for pattern, asset in ASSET_PATTERNS:
        if re.search(pattern, q):
            return asset
    return ""


def _extract_threshold(question: str) -> float:
    """Extract price threshold from question text."""
    for pat in PRICE_PATTERNS:
        match = pat.search(question)
        if match:
            raw = match.group(1).replace(",", "")
            val = float(raw)
            # Handle "k" suffix
            if "k" in question[match.start():match.end()].lower() or val < 500:
                val *= 1000
            return val
    return 0.0


def _detect_direction(question: str) -> str:
    """Detect if question asks about price being above or below threshold."""
    if ABOVE_PATTERNS.search(question):
        return "above"
    if BELOW_PATTERNS.search(question):
        return "below"
    return "above"  # default assumption


def _model_probability_for_market(
    decision: dict,
    threshold: float,
    current_price: float,
    direction: str,
) -> float:
    """
    Convert decision engine output to probability for a specific market question.
    Uses decision action, confidence, expected move, and pressure signals.
    """
    if not threshold or not current_price or current_price <= 0:
        # No threshold? Use decision bias slightly
        action = decision.get("decision", "WAIT")
        confidence = float(decision.get("confidence", 50)) / 100.0
        if action == "BUY":
            return max(0.05, min(0.95, 0.5 + confidence * 0.15))
        if action == "SELL":
            return max(0.05, min(0.95, 0.5 - confidence * 0.15))
        return 0.5

    action = decision.get("decision", "WAIT")
    confidence = float(decision.get("confidence", 50)) / 100.0

    # Distance to threshold as percentage
    distance_pct = (threshold - current_price) / current_price
    if direction == "below":
        distance_pct = -distance_pct

    # Base probability from model direction
    if action == "BUY":
        if direction == "above":
            base = 0.5 + confidence * 0.35
        else:
            base = 0.5 - confidence * 0.35
    elif action == "SELL":
        if direction == "above":
            base = 0.5 - confidence * 0.35
        else:
            base = 0.5 + confidence * 0.35
    elif action in ("WAIT", "AVOID"):
        # WAIT/AVOID: use weak signals from fusion/reasoning
        fusion = decision.get("fusion", {})
        fusion_dir = fusion.get("direction", "neutral")
        if fusion_dir == "bearish":
            base = 0.45 if direction == "above" else 0.55
        elif fusion_dir == "bullish":
            base = 0.55 if direction == "above" else 0.45
        else:
            base = 0.5
    else:
        base = 0.5

    # Distance adjustment: further from threshold → harder to reach
    abs_dist = abs(distance_pct)
    if abs_dist > 0.01:
        penalty = min(abs_dist * 1.5, 0.25)
        if distance_pct > 0:
            # Threshold above current → harder for "above"
            base -= penalty
        else:
            # Threshold below current → easier for "above"
            base += penalty * 0.5

    return max(0.05, min(0.95, round(base, 3)))


async def ingest_polymarket(db) -> dict:
    """
    Fetch live crypto markets from Polymarket, map to assets,
    calculate model probability, store in prediction_markets.
    """
    from prediction.polymarket_client import fetch_markets

    markets = await fetch_markets(limit=30)

    if not markets:
        logger.info("No markets returned from Polymarket API")
        return {"ingested": 0, "total_fetched": 0}

    # Get latest decisions for model probability calculation
    decisions = {}
    for asset in EDGE_ASSETS:
        doc = await db.decision_history.find_one(
            {"asset": asset},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        if doc:
            decisions[asset] = doc

    # Get current prices
    prices = {}
    for asset in EDGE_ASSETS:
        price_doc = await db.exchange_forecasts.find_one(
            {"asset": asset},
            {"_id": 0, "price": 1, "lastPrice": 1},
            sort=[("timestamp", -1)],
        )
        if price_doc:
            prices[asset] = float(price_doc.get("price", 0) or price_doc.get("lastPrice", 0))

    ingested = 0
    now = datetime.now(timezone.utc).isoformat()

    for m in markets:
        asset = _detect_asset(m["question"])
        if not asset or asset not in EDGE_ASSETS:
            continue

        threshold = _extract_threshold(m["question"])
        direction = _detect_direction(m["question"])
        yes_price = m.get("yes_price", 0.5)

        # Calculate model probability
        decision = decisions.get(asset, {})
        current_price = prices.get(asset, 0)
        model_prob = _model_probability_for_market(
            decision, threshold, current_price, direction,
        )

        edge = round(model_prob - yes_price, 4)

        doc = {
            "market_id": m["market_id"],
            "question": m["question"],
            "asset": asset,
            "category": m.get("category", "crypto"),
            "yes_price": yes_price,
            "no_price": m.get("no_price", 0),
            "model_prob": model_prob,
            "edge": edge,
            "threshold": threshold,
            "direction": direction,
            "volume": m.get("volume", 0),
            "liquidity": m.get("liquidity", 0),
            "current_price": current_price,
            "decision_action": decision.get("decision", ""),
            "decision_confidence": float(decision.get("confidence", 0)),
            "updatedAt": now,
        }

        await db.prediction_markets.update_one(
            {"market_id": m["market_id"]},
            {"$set": doc},
            upsert=True,
        )
        ingested += 1

    logger.info(f"Polymarket ingestion: {ingested} markets from {len(markets)} fetched")
    return {
        "ingested": ingested,
        "total_fetched": len(markets),
        "assets_covered": list(set(
            _detect_asset(m["question"]) for m in markets if _detect_asset(m["question"]) in EDGE_ASSETS
        )),
    }
