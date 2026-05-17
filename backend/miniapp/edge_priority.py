"""
Edge Priority Engine v2 — Smart scoring for edge ranking.
==========================================================
score = edge(0.40) + confidence(0.25) + alignment(0.20) + recency(0.10) + conviction(0.05)
"""

from datetime import datetime, timezone


def _clamp(x, lo=0.0, hi=1.0):
    return max(min(x, hi), lo)


def calculate_alignment(edge_direction: str, fusion: dict) -> float:
    """
    Calculate signal alignment from decision fusion data.
    fusion = {"alignedSignals": N, "direction": "bullish/bearish/neutral", "sources": [...]}
    """
    aligned = fusion.get("alignedSignals", 0)
    fusion_dir = fusion.get("direction", "neutral").lower()
    edge_dir_lower = edge_direction.lower()

    # Map edge direction to fusion direction
    edge_is_bullish = edge_dir_lower in ("buy", "bullish")
    fusion_is_bullish = fusion_dir in ("bullish", "buy")
    fusion_is_bearish = fusion_dir in ("bearish", "sell")

    # If fusion direction matches edge direction, alignment is strong
    if (edge_is_bullish and fusion_is_bullish) or (not edge_is_bullish and fusion_is_bearish):
        # More aligned signals = higher score
        if aligned >= 3:
            return 1.0
        if aligned >= 2:
            return 0.8
        if aligned >= 1:
            return 0.6
        return 0.5

    # Opposing direction
    if (edge_is_bullish and fusion_is_bearish) or (not edge_is_bullish and fusion_is_bullish):
        return max(0.1, 0.4 - aligned * 0.1)

    # Neutral
    return 0.5


def calculate_recency(timestamp_str: str) -> float:
    """Calculate recency score from ISO timestamp string."""
    if not timestamp_str:
        return 0.5

    try:
        if isinstance(timestamp_str, datetime):
            created_at = timestamp_str
        else:
            created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        minutes = (now - created_at).total_seconds() / 60

        if minutes <= 60:
            return 1.0
        if minutes <= 240:
            return 0.8
        if minutes <= 720:
            return 0.5
        return 0.2
    except Exception:
        return 0.5


def conviction_bonus(decision_type: str) -> float:
    """Conviction bonus from decision type."""
    if decision_type == "EXTREME":
        return 1.0
    if decision_type == "HIGH_CONVICTION":
        return 0.6
    return 0.0


def calculate_priority(
    edge: float,
    confidence: float,
    fusion: dict = None,
    edge_direction: str = "BUY",
    timestamp: str = None,
    decision_type: str = "NORMAL",
) -> float:
    """
    Calculate edge priority score (0-1).
    Higher = more important edge.
    """
    edge_score = _clamp(abs(edge) / 0.30)
    conf_score = _clamp(confidence)
    align_score = _clamp(calculate_alignment(edge_direction, fusion or {}))
    recency_score = _clamp(calculate_recency(timestamp))
    conv_bonus = _clamp(conviction_bonus(decision_type))

    priority = (
        edge_score * 0.40
        + conf_score * 0.25
        + align_score * 0.20
        + recency_score * 0.10
        + conv_bonus * 0.05
    )

    return round(priority, 4)


def priority_label(score: float) -> str:
    """Human-readable priority label."""
    if score >= 0.80:
        return "ELITE EDGE"
    if score >= 0.68:
        return "LIVE EDGE"
    if score >= 0.55:
        return "STRONG EDGE"
    if score >= 0.40:
        return "WATCHING"
    return "LOW PRIORITY"


def should_alert(priority_score: float, decision_type: str) -> bool:
    """Determine if an edge should trigger an alert."""
    if decision_type == "EXTREME":
        return True
    return priority_score >= 0.62
