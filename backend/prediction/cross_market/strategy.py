"""
Strategy Builder — generates actionable strategies from scored mispricings.

Phase 2 strategies (non-aggressive):
  BUY_YES   — buy YES on the underpriced side
  SELL_YES  — sell YES on the overpriced side
  NO_TRADE  — mispricing exists but not actionable

No complex sizing/execution logic. Just direction + rationale.
"""
import logging
from typing import Optional

logger = logging.getLogger("cross_market.strategy")

# Strategy thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.8
MEDIUM_SCORE_THRESHOLD = 0.6


def build_strategy(scored_mispricing: dict) -> Optional[dict]:
    """Build a trading strategy from a scored mispricing.

    Returns strategy dict or None if not actionable.
    """
    score = scored_mispricing.get("mispricing_score", 0)
    mode = scored_mispricing.get("mode", "SUBSET")
    gap = scored_mispricing.get("gap", 0)
    relation_confidence = scored_mispricing.get("relation_confidence", 0)
    price_a = scored_mispricing.get("price_a", 0)
    price_b = scored_mispricing.get("price_b", 0)

    # Hard filter: relation confidence
    if relation_confidence < 0.6:
        return None

    # Determine action based on mode and direction
    if mode in ("SUBSET", "MONOTONIC"):
        # market_a (higher threshold) is overpriced relative to market_b (lower threshold)
        # Strategy: sell YES on market_a or buy YES on market_b
        if score >= MEDIUM_SCORE_THRESHOLD and gap >= 0.02:
            action_a = "SELL_YES"
            action_b = "BUY_YES"
            rationale = (
                f"Higher threshold ${scored_mispricing.get('threshold_a', 0):,.0f} is overpriced "
                f"at {price_a:.1%} vs lower threshold "
                f"${scored_mispricing.get('threshold_b', 0):,.0f} at {price_b:.1%}"
            )
        else:
            action_a = "NO_TRADE"
            action_b = "NO_TRADE"
            rationale = f"Mispricing detected (gap={gap:.1%}) but below action threshold"

    elif mode == "EQUIVALENT":
        # Equivalent markets with price divergence
        if price_a > price_b:
            action_a = "SELL_YES"
            action_b = "BUY_YES"
        else:
            action_a = "BUY_YES"
            action_b = "SELL_YES"
        rationale = (
            f"Equivalent markets diverge: {price_a:.1%} vs {price_b:.1%}"
        )

    else:
        return None

    strategy_type = "LOGICAL_ARBITRAGE" if action_a != "NO_TRADE" else "NO_TRADE"

    # Confidence level for the strategy
    if relation_confidence >= HIGH_CONFIDENCE_THRESHOLD and score >= 0.7:
        strategy_confidence = "HIGH"
    elif score >= MEDIUM_SCORE_THRESHOLD:
        strategy_confidence = "MEDIUM"
    else:
        strategy_confidence = "LOW"

    return {
        "strategy_type": strategy_type,
        "mode": mode,
        "market_a": scored_mispricing.get("market_a", ""),
        "question_a": scored_mispricing.get("question_a", ""),
        "action_a": action_a,
        "price_a": price_a,
        "threshold_a": scored_mispricing.get("threshold_a", 0),
        "market_b": scored_mispricing.get("market_b", ""),
        "question_b": scored_mispricing.get("question_b", ""),
        "action_b": action_b,
        "price_b": price_b,
        "threshold_b": scored_mispricing.get("threshold_b", 0),
        "mispricing_score": score,
        "actionability_score": scored_mispricing.get("actionability_score", 0),
        "actionability_severity": scored_mispricing.get("actionability_severity", "MEDIUM"),
        "gap": gap,
        "gap_pct": scored_mispricing.get("gap_pct", 0),
        "rationale": rationale,
        "strategy_confidence": strategy_confidence,
        "relation_confidence": relation_confidence,
        "entity": scored_mispricing.get("entity", ""),
        "actionability_breakdown": scored_mispricing.get("actionability_breakdown", {}),
    }


def build_all_strategies(scored_mispricings: list[dict]) -> list[dict]:
    """Build strategies for all scored mispricings.

    Returns list of strategies sorted by mispricing_score desc.
    Filters out NO_TRADE by default but keeps them accessible.
    """
    strategies = []
    no_trades = []

    for sm in scored_mispricings:
        s = build_strategy(sm)
        if s is None:
            continue
        if s["strategy_type"] == "NO_TRADE":
            no_trades.append(s)
        else:
            strategies.append(s)

    strategies.sort(key=lambda x: x["mispricing_score"], reverse=True)

    logger.info(
        f"[Strategy] {len(scored_mispricings)} mispricings → "
        f"{len(strategies)} actionable + {len(no_trades)} NO_TRADE"
    )

    return {
        "actionable": strategies,
        "no_trade": no_trades,
        "total_actionable": len(strategies),
        "total_no_trade": len(no_trades),
    }
