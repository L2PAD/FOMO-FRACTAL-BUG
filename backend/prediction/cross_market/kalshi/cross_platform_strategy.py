"""
Cross-Platform Strategy Builder — generates actionable trading strategies.

Only simple legs:
  LOGICAL_ARBITRAGE: BUY_YES / SELL_YES across platforms
  RELATIVE_VALUE: BUY cheaper / SELL richer (equivalent markets)
  NO_TRADE: detected but not actionable

No sizing, slippage, or execution timing.
"""
import logging

logger = logging.getLogger("cross_market.kalshi.strategy")


def build_strategy(mispricing: dict) -> dict:
    """Build a trading strategy from a scored mispricing."""
    if not mispricing.get("actionable", False):
        return _no_trade(mispricing, "Below actionability threshold")

    constraint_type = mispricing.get("constraint_type", "")
    gap = mispricing.get("gap", 0)
    entity = mispricing.get("entity", "")

    if constraint_type == "SUBSET":
        return _build_subset_strategy(mispricing)
    elif constraint_type == "EQUIVALENT":
        return _build_equivalent_strategy(mispricing)

    return _no_trade(mispricing, "Unknown constraint type")


def _build_subset_strategy(m: dict) -> dict:
    """SUBSET: stricter market overpriced → sell stricter, buy looser."""
    poly_price = m.get("poly_price", 0) or 0
    kalshi_price = m.get("kalshi_price", 0) or 0

    # Determine which side is overpriced
    # In SUBSET constraint, if subset_prob > superset_prob, subset is overpriced
    poly_id = m.get("poly_market_id", "")
    kalshi_id = m.get("kalshi_market_id", "")

    # If Kalshi price > Poly price (and Kalshi is stricter subset),
    # then Kalshi is overpriced → SELL Kalshi, BUY Poly
    if kalshi_price > poly_price:
        legs = [
            {"platform": "polymarket", "market_id": poly_id, "action": "BUY_YES",
             "price": poly_price, "threshold": m.get("poly_threshold", 0)},
            {"platform": "kalshi", "market_id": kalshi_id, "action": "SELL_YES",
             "price": kalshi_price, "threshold": m.get("kalshi_threshold", 0)},
        ]
        reasoning = [
            f"Kalshi (${m.get('kalshi_threshold', 0):,.0f}) is stricter condition",
            f"Stricter at {kalshi_price:.1%} > looser at {poly_price:.1%}",
            "Logical arbitrage: sell overpriced stricter, buy underpriced looser",
        ]
    else:
        legs = [
            {"platform": "kalshi", "market_id": kalshi_id, "action": "BUY_YES",
             "price": kalshi_price, "threshold": m.get("kalshi_threshold", 0)},
            {"platform": "polymarket", "market_id": poly_id, "action": "SELL_YES",
             "price": poly_price, "threshold": m.get("poly_threshold", 0)},
        ]
        reasoning = [
            f"Polymarket (${m.get('poly_threshold', 0):,.0f}) is stricter condition",
            f"Stricter at {poly_price:.1%} > looser at {kalshi_price:.1%}",
            "Logical arbitrage: sell overpriced stricter, buy underpriced looser",
        ]

    return {
        "strategy_type": "LOGICAL_ARBITRAGE",
        "cluster_id": m.get("cluster_id", ""),
        "entity": m.get("entity", ""),
        "edge_case_type": m.get("edge_case_type", "UNKNOWN"),
        "legs": legs,
        "edge": m.get("gap", 0),
        "edge_pct": m.get("gap_pct", 0),
        "score": m.get("score", 0),
        "actionability_score": m.get("actionability_score", 0),
        "severity": m.get("severity", "MEDIUM"),
        "confidence": m.get("components", {}).get("relation_confidence", 0),
        "actionable": True,
        "reasoning": reasoning,
        "risks": [
            "Low liquidity spike on either side",
            "Fast correction before execution",
            "Platform-specific settlement differences",
        ],
    }


def _build_equivalent_strategy(m: dict) -> dict:
    """EQUIVALENT: same condition, price divergence → buy cheap, sell expensive."""
    poly_price = m.get("poly_price", 0) or 0
    kalshi_price = m.get("kalshi_price", 0) or 0
    poly_id = m.get("poly_market_id", "")
    kalshi_id = m.get("kalshi_market_id", "")

    if poly_price < kalshi_price:
        buy_platform, sell_platform = "polymarket", "kalshi"
        buy_id, sell_id = poly_id, kalshi_id
        buy_price, sell_price = poly_price, kalshi_price
        buy_threshold = m.get("poly_threshold", 0)
        sell_threshold = m.get("kalshi_threshold", 0)
    else:
        buy_platform, sell_platform = "kalshi", "polymarket"
        buy_id, sell_id = kalshi_id, poly_id
        buy_price, sell_price = kalshi_price, poly_price
        buy_threshold = m.get("kalshi_threshold", 0)
        sell_threshold = m.get("poly_threshold", 0)

    legs = [
        {"platform": buy_platform, "market_id": buy_id, "action": "BUY_YES",
         "price": buy_price, "threshold": buy_threshold},
        {"platform": sell_platform, "market_id": sell_id, "action": "SELL_YES",
         "price": sell_price, "threshold": sell_threshold},
    ]

    return {
        "strategy_type": "RELATIVE_VALUE",
        "cluster_id": m.get("cluster_id", ""),
        "entity": m.get("entity", ""),
        "edge_case_type": m.get("edge_case_type", "UNKNOWN"),
        "legs": legs,
        "edge": m.get("gap", 0),
        "edge_pct": m.get("gap_pct", 0),
        "score": m.get("score", 0),
        "actionability_score": m.get("actionability_score", 0),
        "severity": m.get("severity", "MEDIUM"),
        "confidence": m.get("components", {}).get("relation_confidence", 0),
        "actionable": True,
        "reasoning": [
            f"Equivalent conditions on both platforms (~${m.get('poly_threshold', 0):,.0f})",
            f"Price divergence: {buy_price:.1%} vs {sell_price:.1%}",
            f"Buy cheaper ({buy_platform}), sell richer ({sell_platform})",
        ],
        "risks": [
            "Settlement wording differences",
            "Low liquidity on one side",
            "Fast convergence before execution",
        ],
    }


def _no_trade(m: dict, reason: str) -> dict:
    return {
        "strategy_type": "NO_TRADE",
        "cluster_id": m.get("cluster_id", ""),
        "entity": m.get("entity", ""),
        "edge_case_type": m.get("edge_case_type", "UNKNOWN"),
        "legs": [],
        "edge": m.get("gap", 0),
        "edge_pct": m.get("gap_pct", 0),
        "score": m.get("score", 0),
        "actionability_score": m.get("actionability_score", 0),
        "severity": m.get("severity", "MEDIUM"),
        "confidence": 0,
        "actionable": False,
        "reasoning": [reason],
        "risks": [],
    }


def build_all_strategies(mispricings: list[dict]) -> dict:
    """Build strategies for all scored mispricings."""
    actionable = []
    no_trade = []

    for m in mispricings:
        s = build_strategy(m)
        if s["strategy_type"] == "NO_TRADE":
            no_trade.append(s)
        else:
            actionable.append(s)

    actionable.sort(key=lambda x: x["actionability_score"], reverse=True)

    logger.info(
        f"[CrossPlatformStrategy] {len(mispricings)} mispricings → "
        f"{len(actionable)} actionable + {len(no_trade)} NO_TRADE"
    )

    return {
        "actionable": actionable,
        "no_trade": no_trade,
        "total_actionable": len(actionable),
        "total_no_trade": len(no_trade),
    }
