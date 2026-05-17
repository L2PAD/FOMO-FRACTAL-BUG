"""
Real Edge Filter — distinguishes real arbitrage from fake edge.

Runs AFTER mispricing scoring, BEFORE strategy generation.

Components:
  liquidity_balance * 0.30
  spread_quality * 0.25
  parser_confidence * 0.20
  timing_alignment * 0.15
  stability * 0.10

Rules:
  real_edge_score < 0.55 → DROP
  real_edge_score < 0.65 → DOWNGRADE severity
  real_edge_score >= 0.65 → VERIFIED EDGE

Trap Detection:
  ASYMMETRIC_LIQUIDITY_TRAP → liquidity_ratio > 5x → downgrade, actionability *= 0.8
  SPREAD_ASYMMETRY_TRAP → spread_ratio > 3x → downgrade
"""
import logging

logger = logging.getLogger("cross_market.kalshi.real_edge")

# Real edge score weights
RE_W_LIQUIDITY_BALANCE = 0.30
RE_W_SPREAD_QUALITY = 0.25
RE_W_PARSER_CONF = 0.20
RE_W_TIMING = 0.15
RE_W_STABILITY = 0.10

# Thresholds
RE_DROP_THRESHOLD = 0.55
RE_DOWNGRADE_THRESHOLD = 0.65

# Trap thresholds
LIQUIDITY_RATIO_TRAP = 5.0
SPREAD_RATIO_TRAP = 3.0


def _liquidity_balance(vol_a: float, vol_b: float) -> float:
    """Balance score: how symmetric is liquidity between platforms."""
    a = max(vol_a or 0, 1)
    b = max(vol_b or 0, 1)
    ratio = min(a, b) / max(a, b)
    # ratio: 1.0 = perfectly balanced, 0.0 = one side empty
    if ratio >= 0.5:
        return 1.0
    elif ratio >= 0.2:
        return 0.8
    elif ratio >= 0.05:
        return 0.6
    elif ratio >= 0.01:
        return 0.4
    return 0.2


def _spread_quality(spread_a: float | None, spread_b: float | None) -> float:
    """How tight are spreads on both sides."""
    spreads = [s for s in [spread_a, spread_b] if s is not None and s > 0]
    if not spreads:
        return 0.7  # unknown → neutral
    max_s = max(spreads)
    if max_s <= 0.01:
        return 1.0
    elif max_s <= 0.02:
        return 0.9
    elif max_s <= 0.03:
        return 0.75
    elif max_s <= 0.05:
        return 0.6
    return 0.3


def _timing_alignment(expiry_a: float | None, expiry_b: float | None) -> float:
    """How aligned are the expiry times."""
    if not expiry_a or not expiry_b:
        return 0.7  # unknown → neutral
    diff_hours = abs(expiry_a - expiry_b) / 3_600_000
    if diff_hours <= 24:
        return 1.0
    elif diff_hours <= 48:
        return 0.8
    elif diff_hours <= 168:
        return 0.6
    return 0.4


def _stability_score(price_a: float, price_b: float) -> float:
    """Simple stability check based on current prices.

    In future: compare with historical prices to detect sudden spikes.
    For now: if prices are very low (close to 0), they're more volatile.
    """
    min_price = min(price_a or 0, price_b or 0)
    if min_price <= 0.005:
        return 0.7  # very low price = less stable
    return 1.0


def _detect_traps(
    vol_a: float, vol_b: float,
    spread_a: float | None, spread_b: float | None,
) -> list[str]:
    """Detect execution traps."""
    traps = []
    a = max(vol_a or 0, 1)
    b = max(vol_b or 0, 1)

    liq_ratio = max(a, b) / min(a, b)
    if liq_ratio > LIQUIDITY_RATIO_TRAP:
        traps.append("ASYMMETRIC_LIQUIDITY_TRAP")

    spreads = [s for s in [spread_a, spread_b] if s is not None and s > 0]
    if len(spreads) == 2:
        sp_ratio = max(spreads) / min(spreads)
        if sp_ratio > SPREAD_RATIO_TRAP:
            traps.append("SPREAD_ASYMMETRY_TRAP")

    return traps


def compute_real_edge_score(
    mispricing: dict,
    poly_market: dict | None = None,
    kalshi_market: dict | None = None,
) -> dict:
    """Compute real edge score and trap flags for a mispricing.

    Returns dict with real_edge_score, trap_flags, edge_badge, and modifiers.
    """
    poly_market = poly_market or {}
    kalshi_market = kalshi_market or {}

    poly_vol = poly_market.get("volume", 0) or 0
    kalshi_vol = kalshi_market.get("volume", 0) or 0
    poly_spread = poly_market.get("spread")
    kalshi_spread = kalshi_market.get("spread")
    poly_expiry = poly_market.get("expiry_ts")
    kalshi_expiry = kalshi_market.get("expiry_ts")
    poly_price = mispricing.get("poly_price", 0) or 0
    kalshi_price = mispricing.get("kalshi_price", 0) or 0

    components = mispricing.get("components", {})
    parser_conf = components.get("parser_confidence", 0.7)

    # Compute sub-scores
    liq_balance = _liquidity_balance(poly_vol, kalshi_vol)
    spread_qual = _spread_quality(poly_spread, kalshi_spread)
    timing = _timing_alignment(poly_expiry, kalshi_expiry)
    stability = _stability_score(poly_price, kalshi_price)

    # Real edge score
    real_edge_score = round(
        liq_balance * RE_W_LIQUIDITY_BALANCE
        + spread_qual * RE_W_SPREAD_QUALITY
        + parser_conf * RE_W_PARSER_CONF
        + timing * RE_W_TIMING
        + stability * RE_W_STABILITY,
        4,
    )

    # Detect traps
    trap_flags = _detect_traps(poly_vol, kalshi_vol, poly_spread, kalshi_spread)

    # Apply trap penalties (downgrade, not drop)
    actionability_modifier = 1.0
    if "ASYMMETRIC_LIQUIDITY_TRAP" in trap_flags:
        actionability_modifier *= 0.8
    if "SPREAD_ASYMMETRY_TRAP" in trap_flags:
        actionability_modifier *= 0.9

    # Determine badge
    if real_edge_score >= RE_DOWNGRADE_THRESHOLD and not trap_flags:
        edge_badge = "verified_edge"
    elif real_edge_score < RE_DROP_THRESHOLD:
        edge_badge = "drop"
    else:
        edge_badge = "execution_risk"

    return {
        "real_edge_score": real_edge_score,
        "trap_flags": trap_flags,
        "edge_badge": edge_badge,
        "actionability_modifier": actionability_modifier,
        "real_edge_components": {
            "liquidity_balance": round(liq_balance, 3),
            "spread_quality": round(spread_qual, 3),
            "parser_confidence": round(parser_conf, 3),
            "timing_alignment": round(timing, 3),
            "stability": round(stability, 3),
        },
    }


def apply_real_edge_filter(mispricings: list[dict], poly_markets_map: dict, kalshi_markets_map: dict) -> list[dict]:
    """Apply real edge filter to scored mispricings.

    - < 0.55 → DROP (remove from list)
    - < 0.65 → DOWNGRADE severity one level
    - >= 0.65 → keep as is (verified edge)

    Also applies trap penalties to actionability.
    """
    filtered = []

    for m in mispricings:
        poly_id = m.get("poly_market_id", "")
        kalshi_id = m.get("kalshi_market_id", "")

        result = compute_real_edge_score(
            m,
            poly_market=poly_markets_map.get(poly_id),
            kalshi_market=kalshi_markets_map.get(kalshi_id),
        )

        # DROP if too low
        if result["edge_badge"] == "drop":
            logger.debug(f"[RealEdge] DROP {m.get('entity')} — score={result['real_edge_score']}")
            continue

        # Merge real edge data into mispricing
        m["real_edge_score"] = result["real_edge_score"]
        m["trap_flags"] = result["trap_flags"]
        m["edge_badge"] = result["edge_badge"]
        m["real_edge_components"] = result["real_edge_components"]

        # Apply trap modifier to actionability
        modifier = result["actionability_modifier"]
        if modifier < 1.0:
            old_act = m.get("actionability_score", 0)
            m["actionability_score"] = round(old_act * modifier, 4)

        # DOWNGRADE severity if borderline
        if result["real_edge_score"] < RE_DOWNGRADE_THRESHOLD:
            severity = m.get("severity", "MEDIUM")
            if severity == "STRONG":
                m["severity"] = "HIGH"
            elif severity == "HIGH":
                m["severity"] = "MEDIUM"
            m["edge_badge"] = "execution_risk"

        # Re-check actionable after modifier
        m["actionable"] = m.get("actionability_score", 0) >= 0.65

        filtered.append(m)

    logger.info(
        f"[RealEdgeFilter] {len(mispricings)} → {len(filtered)} "
        f"(dropped {len(mispricings) - len(filtered)})"
    )
    return filtered
