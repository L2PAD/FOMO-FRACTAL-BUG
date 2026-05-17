"""
Event Decision Engine — picks ONE best action per event card.

Pipeline:
  1. Rank all outcomes by composite score
  2. Resolve sibling conflicts (collapse similar adjacent picks)
  3. Select best pick + optional secondary
  4. Score conviction
  5. Compute edge quality
  6. Apply gates (confidence, edge quality, execution)
  7. Resolve event action (BUY_YES / BUY_NO / WATCH / AVOID)
  8. Build human-readable summary with drivers/risks
"""
import math
import logging

logger = logging.getLogger("feed.event_decision")

# Thresholds
STRONG_EDGE = 0.06
WATCH_EDGE = 0.025
MIN_CONFIDENCE = 0.4
SIBLING_COLLAPSE_THRESHOLD = 0.015

# Confidence numeric mapping
CONF_NUM = {"high": 0.8, "medium": 0.55, "low": 0.3}


def decide_event(event: dict, outcome_overlays: list[dict],
                 structure_analysis: dict | None = None) -> dict:
    """Main entry — produce a single event-level decision."""
    if not outcome_overlays:
        return _empty_decision(event)

    # 1. Rank outcomes
    ranked = _rank_outcomes(outcome_overlays)

    # 2. Resolve sibling conflicts
    resolved = _resolve_siblings(ranked)

    # 3. Select best pick
    primary, secondaries = _select_best_pick(resolved)

    # 4. Score conviction
    conviction = _score_conviction(primary, outcome_overlays, structure_analysis)

    # 5. Compute edge quality for primary
    edge_quality = _compute_edge_quality(primary, event) if primary else {"score": 0, "label": "low"}

    # 6. Apply gates + resolve action
    action, urgency = _resolve_action_gated(primary, conviction, edge_quality)

    # 7. Build summary with structured why (drivers + risks)
    summary, why = _build_summary(event, primary, action, conviction, structure_analysis, edge_quality)

    # 8. Count outcomes
    top_outcomes = resolved[:5]
    outcomes_with_edge = len([o for o in outcome_overlays if abs(o.get("edge", 0)) > 0.02])

    # 9. Outcome competition signal
    viable = len([o for o in outcome_overlays if abs(o.get("edge", 0)) > 0.03])
    if viable == 0:
        competition = "no_edge"
    elif viable == 1:
        competition = "clear_dominant"
    else:
        competition = f"{viable}_competing"

    return {
        "event_id": event.get("event_id", ""),
        "action": action,
        "urgency": urgency,
        "confidence": conviction,
        "edge_quality": edge_quality["label"],
        "summary": summary,
        "why": why,
        "competition": competition,
        "best_pick": _mini(primary) if primary else None,
        "best_no_trade": _find_best_no(outcome_overlays),
        "strongest_edge": _mini(ranked[0]) if ranked else None,
        "top_outcomes": [_mini(o) for o in top_outcomes],
        "outcomes_analyzed": len(outcome_overlays),
        "outcomes_with_edge": outcomes_with_edge,
        "structure": _structure_summary(structure_analysis) if structure_analysis else None,
    }


def _rank_outcomes(overlays: list[dict]) -> list[dict]:
    """Rank outcomes by composite score."""
    scored = []
    for o in overlays:
        edge = abs(o.get("edge", 0))
        conf_score = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(o.get("confidence", "low"), 0.3)

        exec_score = 0.5
        exec_info = o.get("execution", {})
        if isinstance(exec_info, dict):
            style = exec_info.get("style", "")
            if style == "MARKET_OK":
                exec_score = 0.9
            elif style == "LIMIT_PREFERRED":
                exec_score = 0.7
            elif style == "LIMIT_ONLY":
                exec_score = 0.4

        struct_edge = abs(o.get("structure_edge", 0))

        composite = (
            edge * 0.40
            + conf_score * 0.25
            + exec_score * 0.15
            + struct_edge * 0.20
        )

        scored.append({**o, "_composite": round(composite, 4)})

    scored.sort(key=lambda x: x["_composite"], reverse=True)
    return scored


def _resolve_siblings(ranked: list[dict]) -> list[dict]:
    """Collapse adjacent outcomes with similar scores."""
    if len(ranked) <= 2:
        return ranked

    resolved = [ranked[0]]
    for i in range(1, len(ranked)):
        curr = ranked[i]
        prev = resolved[-1]

        # Check if outcomes are "siblings" (very similar composite)
        score_diff = abs(prev["_composite"] - curr["_composite"])
        edge_diff = abs(abs(prev.get("edge", 0)) - abs(curr.get("edge", 0)))

        if score_diff < SIBLING_COLLAPSE_THRESHOLD and edge_diff < 0.015:
            # Skip — too similar to previous, keep the first (higher score)
            continue
        resolved.append(curr)

    return resolved


def _select_best_pick(resolved: list[dict]) -> tuple:
    """Select primary and secondary picks."""
    if not resolved:
        return None, []

    primary = resolved[0]

    # Must have minimum composite score
    if primary["_composite"] < 0.02:
        return None, []

    # Secondary: distinct from primary, must have decent score
    secondaries = []
    for o in resolved[1:3]:
        if o["_composite"] > 0.015:
            secondaries.append(o)

    return primary, secondaries


def _score_conviction(primary: dict | None, all_overlays: list[dict],
                      structure: dict | None) -> str:
    """Score conviction level for the event."""
    if not primary:
        return "low"

    score = 0
    edge = abs(primary.get("edge", 0))
    conf = primary.get("confidence", "low")

    if edge > 0.08:
        score += 3
    elif edge > 0.04:
        score += 2
    elif edge > 0.02:
        score += 1

    if conf == "high":
        score += 2
    elif conf == "medium":
        score += 1

    exec_info = primary.get("execution", {})
    if isinstance(exec_info, dict):
        if exec_info.get("style") in ("MARKET_OK", "LIMIT_PREFERRED"):
            score += 1
        if exec_info.get("slippage_risk") == "low":
            score += 1

    if structure and structure.get("ladder_quality", 0) > 0.8:
        score += 1

    # Consistency: do multiple outcomes agree on direction?
    same_dir = sum(1 for o in all_overlays
                   if (o.get("edge", 0) > 0) == (primary.get("edge", 0) > 0))
    if same_dir > len(all_overlays) * 0.6:
        score += 1

    if score >= 6:
        return "high"
    elif score >= 3:
        return "medium"
    return "low"


def _resolve_action(primary: dict | None, conviction: str) -> tuple[str, str]:
    """Legacy — kept for reference. Use _resolve_action_gated instead."""
    return _resolve_action_gated(primary, conviction, {"score": 0.5, "label": "medium"})


def _compute_edge_quality(primary: dict, event: dict) -> dict:
    """Compute edge quality — how trustworthy is the detected edge."""
    edge = abs(primary.get("edge", 0))
    conf_str = primary.get("confidence", "low")
    conf = CONF_NUM.get(conf_str, 0.3)

    # Liquidity from market or event
    liquidity = event.get("liquidity", 0)
    liq_score = min(math.log10(max(liquidity, 1) + 1) / 6, 1.0)

    exec_info = primary.get("execution", {}) or {}
    exec_quality = {"MARKET_OK": 0.9, "LIMIT_PREFERRED": 0.7, "LIMIT_ONLY": 0.4}.get(
        exec_info.get("style", ""), 0.5
    )

    score = max(0, min(1,
        edge * 0.4
        + conf * 0.25
        + liq_score * 0.15
        + exec_quality * 0.20
    ))

    if score >= 0.55:
        label = "high"
    elif score >= 0.35:
        label = "medium"
    else:
        label = "low"

    return {"score": round(score, 4), "label": label}


def _resolve_action_gated(primary: dict | None, conviction: str,
                          edge_quality: dict) -> tuple[str, str]:
    """Resolve event action with confidence gate, edge quality gate,
    and execution filtering."""
    if not primary:
        return "WATCH", "watch"

    edge = primary.get("edge", 0)
    abs_edge = abs(edge)
    conf_num = CONF_NUM.get(conviction, 0.3)
    eq_score = edge_quality.get("score", 0)

    # ── Gate 1: Confidence Gate ──
    if conf_num < 0.4:
        return "AVOID", "watch"

    # ── Gate 2: Edge Quality Gate ──
    if eq_score < 0.3:
        return "AVOID", "watch"
    if eq_score < 0.4:
        return "WATCH", "watch"

    # ── Gate 3: Execution Filtering ──
    exec_info = primary.get("execution", {}) or {}
    slippage = exec_info.get("slippage_risk", "medium")
    style = exec_info.get("style", "")

    # High slippage downgrades action
    slippage_penalty = slippage == "high"
    illiquid = style == "LIMIT_ONLY"

    # ── Resolve base action ──
    if conf_num < 0.5 and abs_edge < WATCH_EDGE:
        return "WATCH", "watch"

    if edge > STRONG_EDGE and conviction in ("high", "medium"):
        action = "BUY_YES"
        urgency = "now" if conviction == "high" else "soon"
    elif edge < -STRONG_EDGE and conviction in ("high", "medium"):
        action = "BUY_NO"
        urgency = "now" if conviction == "high" else "soon"
    elif abs_edge > WATCH_EDGE:
        action = "WATCH"
        urgency = "watch"
    else:
        return "WATCH", "watch"

    # ── Apply execution downgrade ──
    if slippage_penalty and action in ("BUY_YES", "BUY_NO"):
        urgency = "soon"  # Downgrade from NOW to SOON

    if illiquid and action in ("BUY_YES", "BUY_NO"):
        urgency = "soon"

    # ── Confidence < 0.6 disables NOW urgency ──
    if conf_num < 0.6 and urgency == "now":
        urgency = "soon"

    return action, urgency


def _build_summary(event: dict, primary: dict | None, action: str,
                   conviction: str, structure: dict | None,
                   edge_quality: dict | None = None) -> tuple[str, list[str]]:
    """Build 1-line summary + why reasons (drivers + risks)."""
    if not primary:
        return "No clear trading opportunity", []

    edge_pct = abs(primary.get("edge_pct", 0))
    market_id = primary.get("market_id", "")

    why = list(primary.get("drivers", []))

    if action == "BUY_YES":
        summary = f"YES looks underpriced by {edge_pct}%"
        if structure and structure.get("best_pick") == market_id:
            why.append("Ladder structure confirms mispricing")
    elif action == "BUY_NO":
        summary = f"Market overpricing by {edge_pct}%"
    elif edge_pct > 3:
        summary = f"Potential {edge_pct}% mispricing — watching"
    else:
        summary = "Market appears fairly priced"

    if conviction == "high":
        why.append("High conviction — multiple signals align")

    # Add risk warnings
    exec_info = primary.get("execution", {}) or {}
    if exec_info.get("slippage_risk") == "high":
        why.append("Risk: High slippage — use limit orders")
    if exec_info.get("style") == "LIMIT_ONLY":
        why.append("Risk: Thin orderbook — limit only")

    eq = edge_quality or {}
    if eq.get("label") == "low":
        why.append("Risk: Low edge quality — be cautious")

    return summary, why[:5]


def _find_best_no(overlays: list[dict]) -> dict | None:
    """Find best BUY_NO opportunity."""
    no_picks = [o for o in overlays if o.get("edge", 0) < -0.03]
    if not no_picks:
        return None
    no_picks.sort(key=lambda x: x["edge"])
    return _mini(no_picks[0])


def _mini(o: dict) -> dict:
    """Compact overlay for card display."""
    return {
        "market_id": o.get("market_id", ""),
        "fair_prob": o.get("fair_prob"),
        "market_prob": o.get("market_prob"),
        "edge": o.get("edge"),
        "edge_pct": o.get("edge_pct"),
        "confidence": o.get("confidence"),
        "action": o.get("action"),
        "urgency": o.get("urgency"),
        "execution": o.get("execution"),
        "drivers": o.get("drivers", []),
        "structure_edge": o.get("structure_edge"),
    }


def _structure_summary(analysis: dict) -> dict:
    """Compact structure info for UI."""
    return {
        "ladder_quality": analysis.get("ladder_quality"),
        "best_pick": analysis.get("best_pick"),
        "dominant_issue": analysis.get("dominant_issue"),
        "monotonic": analysis.get("monotonic"),
    }


def _empty_decision(event: dict) -> dict:
    return {
        "event_id": event.get("event_id", ""),
        "action": "WATCH",
        "urgency": "watch",
        "confidence": "low",
        "edge_quality": "low",
        "summary": "No analysis available",
        "why": [],
        "competition": "no_edge",
        "best_pick": None,
        "best_no_trade": None,
        "strongest_edge": None,
        "top_outcomes": [],
        "outcomes_analyzed": 0,
        "outcomes_with_edge": 0,
        "structure": None,
    }
