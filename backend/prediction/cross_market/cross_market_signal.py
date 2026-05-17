"""
Cross-Market Signal — generates signals from detected violations and structure analysis.

Phase 1 signals:
  LADDER_VIOLATION   — monotonicity broken in price ladder
  STRUCTURE_MISMATCH — subset priced above superset
  LADDER_GAP         — unusually large price gap between adjacent thresholds
"""
import logging

logger = logging.getLogger("cross_market.signal")


def generate_signals(parsed_topic: dict, relations: list[dict], violations: list[dict]) -> list[dict]:
    """Generate cross-market signals from a topic's analysis."""
    signals = []

    # Signal 1: Structure violations (mode-aware)
    for v in violations:
        relation_mode = v.get("relation_mode", "SUBSET")

        if relation_mode == "EQUIVALENT":
            signal_type = "EQUIVALENT_DIVERGENCE"
        elif relation_mode == "MONOTONIC":
            signal_type = "MONOTONIC_BREAK"
        else:
            signal_type = "STRUCTURE_MISMATCH"

        signals.append({
            "type": signal_type,
            "severity": "HIGH" if v["gap"] > 0.03 else "MEDIUM",
            "topic_key": parsed_topic["topic_key"],
            "entity": parsed_topic["entity"],
            "message": v["explanation"],
            "market_a": v["market_a"],
            "market_b": v["market_b"],
            "gap": v["gap"],
            "gap_pct": v["gap_pct"],
            "confidence": v["confidence"],
            "relation_mode": relation_mode,
        })

    # Signal 2: Ladder monotonicity check
    ladder_issues = _check_ladder_monotonicity(parsed_topic)
    for issue in ladder_issues:
        signals.append({
            "type": "LADDER_VIOLATION",
            "severity": "MEDIUM",
            "topic_key": parsed_topic["topic_key"],
            "entity": parsed_topic["entity"],
            **issue,
        })

    # Signal 3: Large gaps in ladder
    gap_signals = _check_ladder_gaps(parsed_topic)
    for gs in gap_signals:
        signals.append({
            "type": "LADDER_GAP",
            "severity": "LOW",
            "topic_key": parsed_topic["topic_key"],
            "entity": parsed_topic["entity"],
            **gs,
        })

    if signals:
        logger.info(f"[Signal] {parsed_topic['topic_key']}: {len(signals)} signals")

    return signals


def _check_ladder_monotonicity(parsed_topic: dict) -> list[dict]:
    """Check if prices in a ladder are monotonically decreasing (for ABOVE thresholds)."""
    if not parsed_topic.get("is_ladder"):
        return []

    markets = parsed_topic.get("parsed_markets", [])
    above_markets = [
        m for m in markets
        if m["direction"] == "ABOVE" and m["threshold"] > 0 and m.get("yes_price") is not None
    ]
    above_markets.sort(key=lambda m: m["threshold"])

    issues = []
    for i in range(len(above_markets) - 1):
        curr = above_markets[i]
        next_m = above_markets[i + 1]

        if curr["yes_price"] is not None and next_m["yes_price"] is not None:
            if next_m["yes_price"] > curr["yes_price"] + 0.005:
                issues.append({
                    "message": (
                        f"Non-monotonic: ${next_m['threshold']:,.0f} at "
                        f"{next_m['yes_price']:.1%} > ${curr['threshold']:,.0f} at "
                        f"{curr['yes_price']:.1%}"
                    ),
                    "market_a": next_m["market_id"],
                    "market_b": curr["market_id"],
                    "gap": round(next_m["yes_price"] - curr["yes_price"], 4),
                    "confidence": 0.90,
                })

    return issues


def _check_ladder_gaps(parsed_topic: dict) -> list[dict]:
    """Detect unusually large gaps between adjacent ladder steps."""
    if not parsed_topic.get("is_ladder"):
        return []

    markets = parsed_topic.get("parsed_markets", [])
    above_markets = [
        m for m in markets
        if m["direction"] == "ABOVE" and m["threshold"] > 0 and m.get("yes_price") is not None
    ]
    above_markets.sort(key=lambda m: m["threshold"])

    if len(above_markets) < 3:
        return []

    # Calculate gaps
    gaps = []
    for i in range(len(above_markets) - 1):
        curr = above_markets[i]
        next_m = above_markets[i + 1]
        price_gap = abs(curr["yes_price"] - next_m["yes_price"])
        gaps.append(price_gap)

    if not gaps:
        return []

    avg_gap = sum(gaps) / len(gaps)
    signals = []

    for i, gap in enumerate(gaps):
        if gap > avg_gap * 2.5 and gap > 0.05:  # Gap 2.5x above average and > 5%
            curr = above_markets[i]
            next_m = above_markets[i + 1]
            signals.append({
                "message": (
                    f"Large gap: ${curr['threshold']:,.0f} ({curr['yes_price']:.1%}) → "
                    f"${next_m['threshold']:,.0f} ({next_m['yes_price']:.1%}) — "
                    f"gap {gap:.1%} vs avg {avg_gap:.1%}"
                ),
                "market_a": curr["market_id"],
                "market_b": next_m["market_id"],
                "gap": round(gap, 4),
                "confidence": 0.75,
            })

    return signals
