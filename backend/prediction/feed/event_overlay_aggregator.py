"""
Event Overlay Aggregator — aggregates outcome-level overlays into event-level card data.

Takes all outcome overlays within an event and produces:
  - bestPick: outcome with highest positive edge
  - bestNoTrade: outcome where NO side has best edge
  - eventAction: primary card-level action
  - eventUrgency: card-level urgency
  - summary: 1-line card summary
"""
import logging

logger = logging.getLogger("feed.event_aggregator")


def aggregate_event_overlay(event: dict, outcome_overlays: list[dict]) -> dict:
    """Aggregate outcome overlays into a single event overlay.

    Args:
        event: normalized event dict
        outcome_overlays: list of overlay dicts for each market in the event
    """
    if not outcome_overlays:
        return _empty_overlay(event)

    # Find best YES pick (highest positive edge)
    yes_picks = [o for o in outcome_overlays if o["edge"] > 0.01]
    yes_picks.sort(key=lambda x: x["edge"], reverse=True)

    # Find best NO pick (most negative edge = best BUY_NO)
    no_picks = [o for o in outcome_overlays if o["edge"] < -0.01]
    no_picks.sort(key=lambda x: x["edge"])

    # Best pick overall
    best_pick = yes_picks[0] if yes_picks else None
    best_no = no_picks[0] if no_picks else None

    # Event-level action
    if best_pick and best_pick["edge"] > 0.05 and best_pick["confidence"] in ("high", "medium"):
        event_action = "BUY_YES"
        event_urgency = best_pick["urgency"]
        primary_overlay = best_pick
    elif best_no and abs(best_no["edge"]) > 0.05 and best_no["confidence"] in ("high", "medium"):
        event_action = "BUY_NO"
        event_urgency = best_no["urgency"]
        primary_overlay = best_no
    elif best_pick:
        event_action = "WATCH"
        event_urgency = "watch"
        primary_overlay = best_pick
    else:
        event_action = "WATCH"
        event_urgency = "watch"
        primary_overlay = outcome_overlays[0] if outcome_overlays else None

    # Strongest edge across all outcomes
    all_sorted = sorted(outcome_overlays, key=lambda x: abs(x["edge"]), reverse=True)
    strongest_edge = all_sorted[0] if all_sorted else None

    # Average confidence
    conf_scores = {"high": 3, "medium": 2, "low": 1}
    avg_conf_score = sum(conf_scores.get(o["confidence"], 1) for o in outcome_overlays) / len(outcome_overlays)
    event_confidence = "high" if avg_conf_score >= 2.5 else "medium" if avg_conf_score >= 1.5 else "low"

    # Summary line
    summary = _build_summary(event, primary_overlay, event_action, best_pick)

    # Best outcomes for card display (top 3 by |edge|)
    top_outcomes = all_sorted[:5]

    return {
        "event_id": event.get("event_id", ""),
        "action": event_action,
        "urgency": event_urgency,
        "confidence": event_confidence,
        "summary": summary,
        "best_pick": _mini_overlay(best_pick) if best_pick else None,
        "best_no_trade": _mini_overlay(best_no) if best_no else None,
        "strongest_edge": _mini_overlay(strongest_edge) if strongest_edge else None,
        "top_outcomes": [_mini_overlay(o) for o in top_outcomes],
        "outcomes_analyzed": len(outcome_overlays),
        "outcomes_with_edge": len(yes_picks) + len(no_picks),
    }


def _mini_overlay(o: dict) -> dict:
    """Compact overlay for card display."""
    return {
        "market_id": o["market_id"],
        "fair_prob": o["fair_prob"],
        "market_prob": o["market_prob"],
        "edge": o["edge"],
        "edge_pct": o["edge_pct"],
        "confidence": o["confidence"],
        "action": o["action"],
        "urgency": o["urgency"],
        "execution": o["execution"],
        "drivers": o["drivers"],
    }


def _build_summary(event: dict, primary: dict | None, action: str,
                   best_pick: dict | None) -> str:
    """Build 1-line card summary."""
    title = event.get("title", "")

    if not primary:
        return f"Monitoring {title}"

    edge_pct = abs(primary.get("edge_pct", 0))

    if action == "BUY_YES" and best_pick:
        return f"YES looks underpriced by {edge_pct}%"
    elif action == "BUY_NO":
        return f"NO side has {edge_pct}% edge"
    elif edge_pct > 3:
        return f"Potential {edge_pct}% mispricing detected"
    else:
        return "Market appears fairly priced — monitoring"


def _empty_overlay(event: dict) -> dict:
    return {
        "event_id": event.get("event_id", ""),
        "action": "WATCH",
        "urgency": "watch",
        "confidence": "low",
        "summary": "No analysis available yet",
        "best_pick": None,
        "best_no_trade": None,
        "strongest_edge": None,
        "top_outcomes": [],
        "outcomes_analyzed": 0,
        "outcomes_with_edge": 0,
    }
