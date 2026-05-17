"""
Confidence-Aware Pipeline — enriches decisions with analytics + trust correction.

Correct pipeline order:
  overlay (fair prob, edge, confidence)
  → calibration (adjustedConfidence)
  → analytics (familyConfidence)
  → effective confidence
  → decision gate
  → sizing gate
  → decision stability (last layer)
  → UI

Called from event_ingestion after decide_event() + position_sizing().
"""
import logging

from prediction.feed.family_confidence import get_family_confidence
from prediction.feed.calibration_state import get_calibration_state
from prediction.feed.effective_confidence import compute_effective_confidence
from prediction.feed.decision_stability import apply_stability

logger = logging.getLogger("feed.confidence_aware")

# Confidence numeric mapping
CONF_NUM = {"high": 0.8, "medium": 0.55, "low": 0.3}

# Human-readable gating reasons
GATING_LABELS = {
    "LOW_EFFECTIVE_CONF": "Low confidence",
    "CONF_WATCH_ONLY": "Confidence supports watch only",
    "NOW_DOWNGRADED": "Urgency downgraded by trust",
    "EDGE_TOO_SMALL": "Weak edge",
    "OVERCONFIDENT": "Confidence overstated",
    "BUY_HYSTERESIS": "BUY preserved (edge still strong)",
    "DECISION_LOCKED": "Decision locked (too many flips)",
    "FLIP_LOCKED": "Flip protection active",
    "BUY_PROTECTED": "BUY protected (edge > 5%)",
    "DIR_FLIP_BLOCKED": "Direction flip blocked (low confidence)",
    "STICKY_NO_CHANGE": "No meaningful change",
    "SIZE_CAPPED_TINY": "Size capped to TINY",
    "SIZE_CAPPED_SMALL": "Size capped to SMALL",
    "SIZE_BLOCKED": "No position allowed",
}


def apply_confidence_aware_pipeline(
    event_overlay: dict,
    sizing: dict,
    family_key: str,
    market_id: str,
    db,
) -> dict:
    """Apply the full confidence-aware pipeline to an event decision.

    Mutates event_overlay and sizing in place, and returns enrichment data.

    Returns dict with: analytics, confidence_meta, gating, stability
    """
    action = event_overlay.get("action", "WATCH")
    urgency = event_overlay.get("urgency", "watch")
    confidence_str = event_overlay.get("confidence", "low")
    conf_num = CONF_NUM.get(confidence_str, 0.3)
    edge = 0
    bp = event_overlay.get("best_pick")
    if bp:
        edge = bp.get("edge", 0)

    # ── Step 1: Calibration ──
    cal = get_calibration_state(family_key, conf_num, db)
    adjusted_conf = cal.get("adjusted_confidence", conf_num)

    # ── Step 2: Family Analytics ──
    family = get_family_confidence(family_key, db)

    # ── Step 3: Effective Confidence ──
    # Stability state unknown yet (first pass), use STABLE
    eff = compute_effective_confidence(
        confidence=conf_num,
        adjusted_confidence=adjusted_conf,
        family_strength=family.get("strength", "UNKNOWN"),
        sample_size=family.get("sample_size", 0),
        stability_state="STABLE",
    )
    effective_conf = eff["effective_confidence"]

    # ── Step 4: Decision Gate ──
    gated_action, gated_urgency, gate_reasons = _apply_decision_gate(
        action=action,
        urgency=urgency,
        effective_confidence=effective_conf,
        edge=abs(edge),
        edge_quality=event_overlay.get("edge_quality", "low"),
        prev_action=None,  # will be handled by stability
    )

    # ── Step 5: Sizing Gate ──
    size_fraction = sizing.get("size_fraction", 0)
    gated_fraction, size_label, size_reason = _apply_sizing_gate(
        effective_conf, size_fraction
    )
    if size_reason:
        gate_reasons.append(size_reason)

    # ── Step 6: Decision Stability (last layer) ──
    stable = apply_stability(
        market_id=market_id,
        new_action=gated_action,
        new_urgency=gated_urgency,
        new_edge=abs(edge),
        new_confidence=effective_conf,
        new_size_label=size_label,
        db=db,
    )

    final_action = stable["action"]
    final_urgency = stable["urgency"]
    final_size = stable["size_label"]
    stability_state = stable["stability_state"]

    all_reasons = gate_reasons + stable.get("stability_reasons", [])
    human_reasons = [GATING_LABELS.get(r, r) for r in all_reasons if r]

    # ── Build analytics block for overlay ──
    analytics = {
        "family_accuracy": family.get("accuracy"),
        "family_strength": family.get("strength", "UNKNOWN"),
        "calibration_state": cal.get("state", "UNKNOWN"),
        "sample_size": family.get("sample_size", 0),
        "adjusted_confidence": round(adjusted_conf, 4),
        "effective_confidence": round(effective_conf, 4),
    }

    gating = {
        "original_action": action,
        "original_urgency": urgency,
        "final_action": final_action,
        "final_urgency": final_urgency,
        "gating_reasons": human_reasons[:5],
        "action_changed": final_action != action,
        "urgency_changed": final_urgency != urgency,
    }

    stability_info = {
        "state": stability_state,
        "reasons": stable.get("stability_reasons", []),
    }

    # ── Apply to overlay ──
    event_overlay["action"] = final_action
    event_overlay["urgency"] = final_urgency
    event_overlay["analytics"] = analytics
    event_overlay["gating"] = gating
    event_overlay["stability"] = stability_info

    # ── Apply to sizing ──
    if final_action in ("WATCH", "AVOID"):
        sizing["size_label"] = "NONE"
        sizing["size_fraction"] = 0
        sizing["size_pct"] = 0
    else:
        sizing["size_label"] = final_size
        sizing["size_fraction"] = gated_fraction
        sizing["size_pct"] = round(gated_fraction * 100, 2)

    return {
        "analytics": analytics,
        "gating": gating,
        "stability": stability_info,
        "confidence_meta": eff,
    }


def _apply_decision_gate(
    action: str,
    urgency: str,
    effective_confidence: float,
    edge: float,
    edge_quality: str,
    prev_action: str | None,
) -> tuple[str, str, list[str]]:
    """Apply confidence-aware decision gating.

    Can downgrade action/urgency but never upgrade.
    """
    reasons = []
    final_action = action
    final_urgency = urgency

    # Gate 1: Effective confidence too low → AVOID
    if effective_confidence < 0.4:
        reasons.append("LOW_EFFECTIVE_CONF")
        return "AVOID", "watch", reasons

    # Gate 2: Low confidence → WATCH only
    if effective_confidence < 0.5:
        if final_action not in ("AVOID", "WATCH"):
            final_action = "WATCH"
            final_urgency = "watch"
            reasons.append("CONF_WATCH_ONLY")

    # Gate 3: Not enough confidence for NOW
    if effective_confidence < 0.6 and final_urgency == "now":
        final_urgency = "soon"
        reasons.append("NOW_DOWNGRADED")

    # Gate 4: Edge too small
    if edge < 0.03 and final_action not in ("AVOID", "WATCH"):
        final_action = "WATCH"
        final_urgency = "watch"
        reasons.append("EDGE_TOO_SMALL")

    # Gate 5: Low edge quality blocks aggressive action
    if edge_quality == "low" and final_action in ("BUY_YES", "BUY_NO"):
        final_action = "WATCH"
        final_urgency = "watch"
        reasons.append("EDGE_TOO_SMALL")

    return final_action, final_urgency, reasons


def _apply_sizing_gate(effective_confidence: float,
                       current_fraction: float) -> tuple[float, str, str | None]:
    """Cap position sizes based on effective confidence.

    Returns (fraction, label, reason_code)
    """
    SIZE_BANDS = {
        "TINY": 0.0025,
        "SMALL": 0.0075,
        "MEDIUM": 0.015,
        "LARGE": 0.025,
        "MAX": 0.04,
    }

    if effective_confidence < 0.4:
        return 0, "NONE", "SIZE_BLOCKED"

    if effective_confidence < 0.5:
        capped = min(current_fraction, SIZE_BANDS["TINY"])
        label = "TINY"
        return capped, label, "SIZE_CAPPED_TINY" if capped < current_fraction else None

    if effective_confidence < 0.6:
        capped = min(current_fraction, SIZE_BANDS["SMALL"])
        label = _fraction_to_label(capped)
        return capped, label, "SIZE_CAPPED_SMALL" if capped < current_fraction else None

    label = _fraction_to_label(current_fraction)
    return current_fraction, label, None


def _fraction_to_label(fraction: float) -> str:
    if fraction <= 0:
        return "NONE"
    if fraction < 0.004:
        return "TINY"
    if fraction < 0.011:
        return "SMALL"
    if fraction < 0.02:
        return "MEDIUM"
    if fraction < 0.032:
        return "LARGE"
    return "MAX"
