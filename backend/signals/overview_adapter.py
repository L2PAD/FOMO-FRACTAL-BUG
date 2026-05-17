"""
Overview Signal Adapter
=======================
Translates V3 engine context data into unified signal context format.
Then calls core_signal_logic.detect_signal_type() — same brain, different input.

Usage:
    ctx = build_overview_context(engine_snapshot)
    signal = detect_signal(ctx)
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("overview_adapter")


def build_overview_context(snapshot: dict) -> dict:
    """
    Build unified signal context from engine_context_snapshot.
    Maps V3 engine data → unified context compatible with detect_signal_type().

    Args:
        snapshot: Document from engine_context_snapshots collection.

    Returns:
        Unified context dict: {mentions, momentum, pressure, alpha, flow,
                               growth_rate, actor_count, setup_type, source}
    """
    setup = snapshot.get("setup_engine", {}).get("primary", {})
    regime = snapshot.get("regime_engine", {}).get("primary", {})
    prob = snapshot.get("probability_layer", {})
    flow = snapshot.get("flow_engine", {})
    liq = snapshot.get("liquidity_map", {})
    risk = snapshot.get("risk_engine", {})

    # ── Setup as pressure signal ──
    setup_type = setup.get("type", "mixed")
    setup_conf = setup.get("confidence", 0)
    continuation = prob.get("continuation", 0)
    pressure = continuation * setup_conf  # engine alignment

    # ── Flow as momentum ──
    flow_strength = flow.get("strength", 0)
    flow_state = flow.get("state", "neutral")

    if "bullish" in flow_state.lower():
        momentum = flow_strength
    elif "bearish" in flow_state.lower():
        momentum = -flow_strength
    else:
        momentum = 0

    # ── Actors ──
    # Actor data comes from os_service; snapshot doesn't contain it directly
    # but we track actor_count from the signal events
    actor_count = 0
    alpha = 0.0

    # ── Liquidity as flow signal ──
    targets = liq.get("target_zones", [])
    flow_score = 0.3
    if targets:
        aligned_targets = sum(1 for t in targets if t.get("confidence", 0) > 0.5)
        flow_score = min(aligned_targets / max(len(targets), 1), 1.0)

    # ── Risk context ──
    risk_level = risk.get("risk_level", "MODERATE").lower()

    return {
        "mentions": 0,  # Overview doesn't have mention counts
        "momentum": momentum,
        "pressure": pressure,
        "alpha": alpha,
        "flow": flow_score,
        "growth_rate": flow_strength if momentum > 0 else -flow_strength if momentum < 0 else 0,
        "actor_count": actor_count,
        "setup_type": setup_type if setup_type != "mixed" else "",
        "source": "overview",
        "asset": snapshot.get("asset", ""),
        "market_context": {
            "regime": regime.get("type", "neutral_chop"),
            "pressure": "bullish" if momentum > 0.1 else "bearish" if momentum < -0.1 else "neutral",
            "ranking": 0,
            "risk": risk_level,
        },
    }


def build_overview_context_with_actors(snapshot: dict, actors: list) -> dict:
    """
    Enhanced version that includes actor data from os_service.
    Call this when actor_radar data is available.
    """
    ctx = build_overview_context(snapshot)

    if actors:
        strong_actors = [a for a in actors if a.get("strength", 0) >= 55]
        ctx["actor_count"] = len(strong_actors)

        # Alpha from actor strength
        if strong_actors:
            avg_strength = sum(a["strength"] for a in strong_actors) / len(strong_actors)
            ctx["alpha"] = min(avg_strength / 100, 1.0)

        # Mention proxy from actor count
        ctx["mentions"] = len(actors)

    return ctx
