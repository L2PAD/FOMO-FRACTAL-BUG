"""
Fair Probability Engine v2 — production model.

fair_prob = market_prob
    + time_decay_adjustment
    + liquidity_adjustment
    + structure_edge
    + volatility_adjustment

No sentiment yet (Phase 3). Focus on market microstructure signals.
"""
import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger("feed.fair_prob")


def compute_fair_prob(market: dict, event_type: str,
                      structure_edge: float = 0,
                      event_context: dict | None = None) -> dict:
    """Compute fair probability with v2 multi-factor model.

    Returns dict with fair_prob, edge, components breakdown.
    """
    market_prob = market.get("yes_price", 0.5)
    if market_prob <= 0 or market_prob >= 1:
        return {"fair_prob": market_prob, "edge": 0, "edge_pct": 0, "components": {}}

    volume = market.get("volume", 0)
    liquidity = market.get("liquidity", 0)
    spread = market.get("spread", 0)
    end_date = (event_context or {}).get("end_date")

    # ── 1. Time Decay Adjustment ──
    time_adj = _time_decay_adjustment(market_prob, end_date)

    # ── 2. Liquidity Adjustment ──
    liq_adj = _liquidity_adjustment(market_prob, volume, liquidity)

    # ── 3. Structure Edge (from Structure Edge Engine) ──
    struct_adj = _clamp(structure_edge, -0.12, 0.12)

    # ── 4. Volatility / Spread Adjustment ──
    vol_adj = _volatility_adjustment(market_prob, spread, volume)

    # ── 5. Event Type Adjustment ──
    type_adj = _event_type_adjustment(market_prob, event_type, volume)

    # ── Combine ──
    fair_prob = (
        market_prob
        + time_adj
        + liq_adj
        + struct_adj
        + vol_adj
        + type_adj
    )

    fair_prob = _clamp(fair_prob, 0.01, 0.99)
    edge = round(fair_prob - market_prob, 4)

    return {
        "fair_prob": round(fair_prob, 4),
        "edge": edge,
        "edge_pct": round(edge * 100, 2),
        "components": {
            "time_decay": round(time_adj, 4),
            "liquidity": round(liq_adj, 4),
            "structure": round(struct_adj, 4),
            "volatility": round(vol_adj, 4),
            "event_type": round(type_adj, 4),
        },
    }


def _time_decay_adjustment(market_prob: float, end_date: str | None) -> float:
    """Markets become more efficient near expiry.
    Far from expiry → more mispricing → pull toward 50%.
    Near expiry → trust market price more."""
    if not end_date:
        return 0

    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_left = (end - now).total_seconds() / 3600

        if hours_left <= 0:
            return 0

        # Factor: 0 (near expiry) to 1 (far out)
        time_factor = _clamp(hours_left / (30 * 24), 0, 1)

        # Far from expiry: pull extreme prices slightly toward center
        if market_prob > 0.7:
            return -time_factor * 0.03
        elif market_prob < 0.3:
            return time_factor * 0.03
        return 0

    except Exception:
        return 0


def _liquidity_adjustment(market_prob: float, volume: float, liquidity: float) -> float:
    """Low liquidity = less price discovery = more potential mispricing.
    High liquidity = trust market price more."""
    if volume <= 0 and liquidity <= 0:
        return 0

    # Log-scale liquidity score (0-1)
    liq_score = _clamp(math.log(max(volume, 1) + 1) / 15, 0, 1)

    # Low liquidity: pull toward 50% (less certainty)
    if liq_score < 0.3:
        pull = (0.5 - market_prob) * 0.06 * (1 - liq_score)
        return _clamp(pull, -0.04, 0.04)

    return 0


def _volatility_adjustment(market_prob: float, spread: float, volume: float) -> float:
    """Wide spread = uncertainty. Recent volume spikes = potential overreaction."""
    adj = 0

    # Wide spread: market is uncertain, pull toward center
    if spread > 0.08:
        adj = (0.5 - market_prob) * 0.04

    return _clamp(adj, -0.03, 0.03)


def _event_type_adjustment(market_prob: float, event_type: str, volume: float) -> float:
    """Event-type-specific adjustments."""
    adj = 0

    if event_type == "direction":
        # Short-term direction bets: market is usually efficient for high volume
        if volume > 50000:
            adj = 0  # Trust the market
        else:
            adj = (0.5 - market_prob) * 0.02

    elif event_type == "fdv":
        # FDV markets: pre-launch hype often overprices YES
        if market_prob > 0.5:
            adj = -0.02
        elif market_prob < 0.15:
            adj = 0.015  # Tail might be underpriced

    elif event_type == "launch":
        # Token launches: deadline asymmetry
        if market_prob < 0.2:
            adj = 0.015

    return _clamp(adj, -0.04, 0.04)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
