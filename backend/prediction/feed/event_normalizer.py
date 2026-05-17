"""
Event Normalizer — transforms raw Gamma API events into normalized domain model.

Gamma event → NormalizedEvent with NormalizedMarket[] (outcomes)
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("feed.normalizer")


def normalize_event(raw_event: dict) -> dict:
    """Transform raw Gamma event into normalized event document."""
    markets = raw_event.get("markets", [])

    # Parse event-level data
    event_id = str(raw_event.get("id", ""))
    title = raw_event.get("title", "") or ""
    slug = raw_event.get("slug", "") or ""
    description = raw_event.get("description", "") or ""
    end_date = raw_event.get("endDate")
    volume = _safe_float(raw_event.get("volume"))
    volume_24h = _safe_float(raw_event.get("volume24hr"))
    liquidity = _safe_float(raw_event.get("liquidity"))
    liquidity_clob = _safe_float(raw_event.get("liquidityClob"))
    enable_order_book = bool(raw_event.get("enableOrderBook"))
    neg_risk = bool(raw_event.get("negRisk"))
    image = raw_event.get("image", "")
    icon = raw_event.get("icon", "")

    # Is this multi-outcome or binary?
    is_multi = len(markets) > 1

    # Normalize each market (outcome)
    normalized_markets = []
    for m in markets:
        nm = normalize_market(m, event_id)
        if nm:
            normalized_markets.append(nm)

    return {
        "event_id": event_id,
        "title": title,
        "slug": slug,
        "description": description,
        "end_date": end_date,
        "volume": volume,
        "volume_24h": volume_24h,
        "liquidity": liquidity,
        "liquidity_clob": liquidity_clob,
        "enable_order_book": enable_order_book,
        "neg_risk": neg_risk,
        "is_multi": is_multi,
        "markets_count": len(normalized_markets),
        "image": image,
        "icon": icon,
        "markets": normalized_markets,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_market(raw_market: dict, event_id: str) -> dict | None:
    """Normalize a single market (outcome) within an event."""
    market_id = str(raw_market.get("id", ""))
    if not market_id:
        return None

    question = raw_market.get("question", "") or ""
    slug = raw_market.get("groupItemTitle", "") or raw_market.get("slug", "") or ""

    # Outcomes and prices
    outcomes = raw_market.get("outcomes", ["Yes", "No"])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = ["Yes", "No"]

    outcome_prices_raw = raw_market.get("outcomePrices", [])
    if isinstance(outcome_prices_raw, str):
        try:
            outcome_prices_raw = json.loads(outcome_prices_raw)
        except Exception:
            outcome_prices_raw = []

    outcome_prices = [_safe_float(p) for p in outcome_prices_raw]

    # CLOB token IDs
    clob_token_ids_raw = raw_market.get("clobTokenIds", [])
    if isinstance(clob_token_ids_raw, str):
        try:
            clob_token_ids_raw = json.loads(clob_token_ids_raw)
        except Exception:
            clob_token_ids_raw = []

    # Prices
    yes_price = outcome_prices[0] if len(outcome_prices) > 0 else 0
    no_price = outcome_prices[1] if len(outcome_prices) > 1 else 1 - yes_price

    best_bid = _safe_float(raw_market.get("bestBid"))
    best_ask = _safe_float(raw_market.get("bestAsk"))
    spread = best_ask - best_bid if best_ask > best_bid else 0

    volume = _safe_float(raw_market.get("volume"))
    liquidity = _safe_float(raw_market.get("liquidity"))

    active = bool(raw_market.get("active"))
    closed = bool(raw_market.get("closed"))

    return {
        "market_id": market_id,
        "event_id": event_id,
        "question": question,
        "group_title": slug,
        "outcomes": outcomes,
        "outcome_prices": outcome_prices,
        "clob_token_ids": clob_token_ids_raw,
        "yes_price": yes_price,
        "no_price": no_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": round(spread, 4),
        "volume": volume,
        "liquidity": liquidity,
        "active": active,
        "closed": closed,
        "end_date": raw_market.get("endDate"),
    }


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
