"""
Outcome Overlay — computes intelligence overlay for each market outcome.

For each outcome market:
  - fair probability (model-based or heuristic)
  - edge (fair - market)
  - confidence
  - action (BUY_YES, BUY_NO, WATCH, AVOID)
  - execution style
  - reasoning
"""
import logging

logger = logging.getLogger("feed.outcome_overlay")


def compute_outcome_overlay(market: dict, event_type: str,
                            fair_prob_result: dict | None = None,
                            structure_edge_val: float = 0) -> dict:
    """Compute overlay for a single market/outcome.

    When fair_prob_result is provided (from fair_prob_v2 engine),
    uses the v2 model. Otherwise falls back to v1 heuristic.
    """
    yes_price = market.get("yes_price", 0.5)
    spread = market.get("spread", 0)
    volume = market.get("volume", 0)
    liquidity = market.get("liquidity", 0)
    best_bid = market.get("best_bid", 0)
    best_ask = market.get("best_ask", 0)

    # --- Fair probability estimation ---
    if fair_prob_result:
        fair_prob = fair_prob_result["fair_prob"]
        edge = fair_prob_result["edge"]
        edge_pct = fair_prob_result["edge_pct"]
    else:
        fair_prob = _estimate_fair_prob(yes_price, spread, volume, liquidity, event_type)
        edge = round(fair_prob - yes_price, 4)
        edge_pct = round(edge * 100, 2)

    # --- Confidence ---
    confidence = _compute_confidence(volume, liquidity, spread, abs(edge))

    # --- Action ---
    action = _determine_action(edge, confidence, spread, liquidity)

    # --- Urgency ---
    urgency = _determine_urgency(abs(edge), confidence, volume)

    # --- Execution ---
    execution = _compute_execution(best_bid, best_ask, spread, liquidity, action)

    # --- Edge drivers ---
    drivers = _build_edge_drivers(edge, spread, volume, liquidity, event_type, yes_price)

    # Add structure context to drivers
    if structure_edge_val > 0.03:
        drivers.insert(0, "Ladder structure confirms underpricing")
    elif structure_edge_val < -0.03:
        drivers.insert(0, "Ladder structure suggests overpricing")

    label = market.get("group_title", "") or (market.get("question", "") or "")[:35]

    return {
        "market_id": market["market_id"],
        "fair_prob": round(fair_prob, 4),
        "market_prob": yes_price,
        "edge": edge,
        "edge_pct": edge_pct,
        "confidence": confidence,
        "action": action,
        "urgency": urgency,
        "execution": execution,
        "drivers": drivers,
        "structure_edge": round(structure_edge_val, 4),
        "_label": label,
    }


def _estimate_fair_prob(yes_price: float, spread: float, volume: float,
                        liquidity: float, event_type: str) -> float:
    """Estimate fair probability using market microstructure signals.

    This is the core model. For v1, uses heuristics based on:
    - Price momentum signal (deviation from 50/50)
    - Spread signal (wide spread = less informed pricing)
    - Volume signal (high volume = more price discovery)
    - Liquidity signal (thin = manipulable)
    """
    if yes_price <= 0 or yes_price >= 1:
        return yes_price

    # Base: market price is informed
    fair = yes_price

    # Spread correction: wide spread means market is less certain
    # If spread > 5%, pull fair toward 50%
    if spread > 0.05:
        spread_pull = min(spread * 0.3, 0.08)
        if yes_price > 0.5:
            fair -= spread_pull * 0.5
        else:
            fair += spread_pull * 0.5

    # Volume signal: low volume = less price discovery = more potential mispricing
    if volume < 5000 and yes_price < 0.3:
        # Low volume + low price = potential underpricing
        fair += 0.02
    elif volume < 5000 and yes_price > 0.7:
        # Low volume + high price = potential overpricing
        fair -= 0.02

    # Liquidity signal
    if liquidity < 1000 and abs(yes_price - 0.5) > 0.2:
        # Thin liquidity + strong conviction = could be manipulated
        # Pull slightly toward center
        fair = fair * 0.95 + 0.5 * 0.05

    # Event type adjustments
    if event_type == "direction":
        # Short-term direction bets: market is usually efficient
        fair = yes_price * 0.95 + fair * 0.05
    elif event_type == "fdv":
        # FDV markets tend to be overpriced pre-launch
        if yes_price > 0.3:
            fair -= 0.03
    elif event_type == "launch":
        # Launch/token markets: deadlines create asymmetry
        if yes_price < 0.2:
            fair += 0.02

    return max(0.01, min(0.99, fair))


def _compute_confidence(volume: float, liquidity: float, spread: float,
                        abs_edge: float) -> str:
    """Determine confidence level."""
    score = 0
    if volume > 100000:
        score += 3
    elif volume > 10000:
        score += 2
    elif volume > 1000:
        score += 1

    if liquidity > 5000:
        score += 2
    elif liquidity > 1000:
        score += 1

    if spread < 0.03:
        score += 2
    elif spread < 0.08:
        score += 1

    if abs_edge > 0.1:
        score += 1
    elif abs_edge > 0.05:
        score += 1

    if score >= 7:
        return "high"
    elif score >= 4:
        return "medium"
    return "low"


def _determine_action(edge: float, confidence: str, spread: float,
                      liquidity: float) -> str:
    """Determine trade action."""
    abs_edge = abs(edge)

    if confidence == "low" and abs_edge < 0.05:
        return "WATCH"
    if spread > 0.15:
        return "AVOID"
    if liquidity < 100:
        return "AVOID"

    if edge > 0.03:
        return "BUY_YES"
    elif edge < -0.03:
        return "BUY_NO"
    elif abs_edge < 0.02:
        return "WATCH"
    return "WATCH"


def _determine_urgency(abs_edge: float, confidence: str, volume: float) -> str:
    """Determine urgency."""
    if abs_edge > 0.1 and confidence in ("high", "medium"):
        return "now"
    if abs_edge > 0.05 and confidence == "high":
        return "now"
    if abs_edge > 0.05:
        return "soon"
    return "watch"


def _compute_execution(best_bid: float, best_ask: float, spread: float,
                       liquidity: float, action: str) -> dict:
    """Compute execution hints."""
    spread_pct = round(spread / best_ask * 100, 2) if best_ask > 0 else 0

    if spread_pct > 10:
        style = "LIMIT_ONLY"
    elif spread_pct > 3:
        style = "LIMIT_PREFERRED"
    elif liquidity > 5000:
        style = "MARKET_OK"
    else:
        style = "LIMIT_PREFERRED"

    slippage_risk = "high" if spread_pct > 8 else "medium" if spread_pct > 3 else "low"

    return {
        "style": style,
        "spread_pct": spread_pct,
        "slippage_risk": slippage_risk,
        "best_bid": best_bid,
        "best_ask": best_ask,
    }


def _build_edge_drivers(edge: float, spread: float, volume: float,
                        liquidity: float, event_type: str,
                        yes_price: float) -> list[str]:
    """Build 1-3 line explanation of edge."""
    drivers = []
    abs_edge = abs(edge)

    if abs_edge > 0.05:
        side = "underpriced" if edge > 0 else "overpriced"
        drivers.append(f"Market appears {side} by {abs(round(edge * 100, 1))}%")

    if spread > 0.05:
        drivers.append(f"Wide spread ({round(spread * 100, 1)}%) creates opportunity")

    if volume < 5000:
        drivers.append("Low volume — less price discovery")
    elif volume > 500000:
        drivers.append("High volume — strong price signal")

    if liquidity < 1000:
        drivers.append("Thin liquidity — use limit orders")

    if not drivers:
        drivers.append("Market appears fairly priced")

    return drivers[:3]
