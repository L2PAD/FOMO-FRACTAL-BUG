"""
Pricing Engine — analyzes what's already priced into the market.

Determines market state from the relationship between fair probability,
implied probability, volume, liquidity, spread, and time to expiry.

States:
  - underpriced: fair >> implied, market hasn't caught up
  - fairly_priced: fair ≈ implied
  - overheated: implied has overshot fair, possibly on hype
  - early_repricing: market just started moving toward fair
  - late_repricing: market almost at fair, edge shrinking
  - priced_in: market fully reflects the thesis
  - panic_move: sharp move on high volume, likely emotional
  - stale_price: low volume/liquidity, price not meaningful

Dimensions beyond edge:
  - time_to_expiry: urgency / decay factor
  - spread_quality: tight / normal / wide
  - volume_profile: dead / thin / moderate / active / heavy
  - liquidity_depth: shallow / moderate / deep
"""
from datetime import datetime, timezone


def analyze(market: dict, fair_prob: float, edge: float) -> dict:
    """
    Determine what's priced into the market.

    Args:
        market: normalized market dict with yes_price, volume, liquidity, spread, end_date
        fair_prob: model's fair probability
        edge: raw edge (fair - implied)

    Returns:
        dict with market_state, description, implied_prob, fair_prob,
              spread_quality, volume_profile, liquidity_depth, days_to_expiry, urgency
    """
    implied = market.get("yes_price", 0.5)
    volume = market.get("volume", 0)
    liquidity = market.get("liquidity", 0)
    spread = market.get("spread", 0)
    end_date = market.get("end_date")

    abs_edge = abs(edge)

    # --- Spread quality ---
    if spread < 0.03:
        spread_quality = "tight"
    elif spread < 0.08:
        spread_quality = "normal"
    elif spread < 0.15:
        spread_quality = "wide"
    else:
        spread_quality = "very_wide"

    # --- Volume profile ---
    if volume < 1000:
        volume_profile = "dead"
    elif volume < 10000:
        volume_profile = "thin"
    elif volume < 50000:
        volume_profile = "moderate"
    elif volume < 200000:
        volume_profile = "active"
    else:
        volume_profile = "heavy"

    # --- Liquidity depth ---
    if liquidity < 5000:
        liquidity_depth = "shallow"
    elif liquidity < 50000:
        liquidity_depth = "moderate"
    else:
        liquidity_depth = "deep"

    # --- Time to expiry ---
    days_to_expiry = _days_to_expiry(end_date)
    if days_to_expiry is not None:
        if days_to_expiry <= 1:
            urgency = "expiring"
        elif days_to_expiry <= 3:
            urgency = "imminent"
        elif days_to_expiry <= 14:
            urgency = "near_term"
        elif days_to_expiry <= 60:
            urgency = "medium_term"
        else:
            urgency = "long_term"
    else:
        urgency = "unknown"

    meta = {
        "spread_quality": spread_quality,
        "volume_profile": volume_profile,
        "liquidity_depth": liquidity_depth,
        "days_to_expiry": days_to_expiry,
        "urgency": urgency,
    }

    # --- Stale detection ---
    if volume_profile == "dead" and liquidity_depth == "shallow":
        return _result("stale_price", "Low volume and liquidity — price unreliable", implied, fair_prob, meta)

    # --- Panic detection: very high volume + large edge ---
    if volume_profile == "heavy" and abs_edge > 0.15:
        return _result("panic_move", "Sharp move on high volume — likely emotional repricing", implied, fair_prob, meta)

    # --- Expiring markets: tighten thresholds ---
    if urgency == "expiring" and abs_edge < 0.05:
        return _result("priced_in", "Expiring soon — residual edge unreliable", implied, fair_prob, meta)

    # --- Priced in: edge < 3% ---
    if abs_edge < 0.03:
        return _result("priced_in", "Market fully reflects current thesis", implied, fair_prob, meta)

    # --- Fairly priced: edge 3-5% ---
    if abs_edge < 0.05:
        return _result("fairly_priced", "Market approximately reflects fair value", implied, fair_prob, meta)

    # --- Overheated: implied overshoots fair ---
    if edge < -0.08:
        return _result("overheated", "Market has overpriced YES beyond model fair value", implied, fair_prob, meta)

    # --- Underpriced vs repricing ---
    if edge > 0.10:
        if volume_profile in ("active", "heavy"):
            return _result("early_repricing", "Market starting to reprice toward fair value on volume", implied, fair_prob, meta)
        return _result("underpriced", "Market hasn't caught up to model fair value", implied, fair_prob, meta)

    if edge > 0.05:
        if volume_profile in ("active", "heavy"):
            return _result("late_repricing", "Market almost at fair value, edge shrinking", implied, fair_prob, meta)
        return _result("underpriced", "Moderate underpricing, low volume suggests opportunity", implied, fair_prob, meta)

    return _result("fairly_priced", "No significant mispricing detected", implied, fair_prob, meta)


def _days_to_expiry(end_date) -> int | None:
    if not end_date:
        return None
    try:
        if isinstance(end_date, str):
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        else:
            end = end_date
        now = datetime.now(timezone.utc)
        delta = (end - now).total_seconds() / 86400
        return max(0, round(delta, 1))
    except Exception:
        return None


def _result(state: str, description: str, implied: float, fair: float, meta: dict) -> dict:
    return {
        "market_state": state,
        "description": description,
        "implied_prob": round(implied, 4),
        "fair_prob": round(fair, 4),
        **meta,
    }
