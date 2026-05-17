"""
Structure Edge Engine — finds mispricing in multi-outcome ladder markets.

For price ladders (BTC above $60k/$65k/$70k/$75k/$80k):
  1. Parse numeric levels from outcome labels
  2. Check monotonicity (probabilities should decrease with higher targets)
  3. Measure local gap anomalies between adjacent outcomes
  4. Measure smoothness (second derivative curvature)
  5. Compute relative value (interpolated expected vs actual)
  6. Score each outcome's structural edge

Only applies to multi-outcome events with parseable numeric levels.
"""
import re
import logging

logger = logging.getLogger("feed.structure_edge")


def analyze_ladder(markets: list[dict]) -> dict | None:
    """Analyze a multi-outcome event for ladder structure edge.

    Args:
        markets: list of normalized market dicts with question, yes_price, market_id

    Returns:
        StructureAnalysis dict or None if not a ladder market.
    """
    # 1. Parse ladder — extract numeric values from outcomes
    ladder = _parse_ladder(markets)
    if not ladder or len(ladder) < 3:
        return None

    # Sort by numeric value ascending
    ladder.sort(key=lambda x: x["numeric_value"])

    n = len(ladder)

    # 2. Monotonic check
    mono = _check_monotonic(ladder)

    # 3-6. Score each outcome
    scored = []
    for i, item in enumerate(ladder):
        local_gap = _local_gap_score(ladder, i)
        smoothness = _smoothness_score(ladder, i)
        relative_value = _relative_value_score(ladder, i)

        structure_edge = _compute_structure_edge(
            local_gap, smoothness, relative_value, mono["penalty"]
        )

        verdict = "FAIR"
        if structure_edge > 0.04:
            verdict = "UNDERPRICED"
        elif structure_edge < -0.04:
            verdict = "OVERPRICED"

        scored.append({
            "market_id": item["market_id"],
            "label": item["label"],
            "numeric_value": item["numeric_value"],
            "market_prob": item["market_prob"],
            "monotonic_ok": mono["ok"],
            "local_gap": round(local_gap, 4),
            "smoothness": round(smoothness, 4),
            "relative_value": round(relative_value, 4),
            "structure_edge": round(structure_edge, 4),
            "verdict": verdict,
        })

    # Find best pick
    underpriced = [s for s in scored if s["verdict"] == "UNDERPRICED"]
    underpriced.sort(key=lambda x: x["structure_edge"], reverse=True)
    best_pick = underpriced[0]["market_id"] if underpriced else None

    # Ladder quality
    ladder_quality = round(1.0 - mono["penalty"], 2)

    # Dominant issue
    issue = None
    if not mono["ok"]:
        issue = "Non-monotonic probability ladder"
    elif any(s["local_gap"] > 0.1 for s in scored):
        issue = "Uneven probability gaps between outcomes"

    return {
        "ladder_quality": ladder_quality,
        "outcomes": scored,
        "best_pick": best_pick,
        "dominant_issue": issue,
        "monotonic": mono["ok"],
        "violations": mono["violations"],
    }


def get_outcome_structure_edge(analysis: dict | None, market_id: str) -> float:
    """Get structure edge for a specific outcome from analysis."""
    if not analysis:
        return 0.0
    for o in analysis.get("outcomes", []):
        if o["market_id"] == market_id:
            return o["structure_edge"]
    return 0.0


# ── Internal helpers ──

def _parse_ladder(markets: list[dict]) -> list[dict] | None:
    """Extract numeric levels from market questions/labels."""
    ladder = []
    for m in markets:
        q = m.get("question", "") or m.get("group_title", "") or ""
        num = _extract_numeric(q)
        if num is not None:
            ladder.append({
                "market_id": m["market_id"],
                "label": m.get("group_title", "") or q[:30],
                "numeric_value": num,
                "market_prob": m.get("yes_price", 0),
            })
    return ladder if len(ladder) >= 3 else None


def _extract_numeric(text: str) -> float | None:
    """Extract price/numeric threshold from question text."""
    t = text.lower().replace(",", "").replace("$", "").replace("€", "")

    # Match patterns: "above 70000", "70k", "$1.5B", "2100", etc.
    # Try billions first
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:b|billion)', t)
    if m:
        return float(m.group(1)) * 1_000_000_000

    # Millions
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|million)', t)
    if m:
        return float(m.group(1)) * 1_000_000

    # K suffix
    m = re.search(r'(\d+(?:\.\d+)?)\s*k\b', t)
    if m:
        return float(m.group(1)) * 1000

    # Plain number (at least 3 digits to avoid matching dates/percentages)
    m = re.search(r'\b(\d{3,}(?:\.\d+)?)\b', t)
    if m:
        return float(m.group(1))

    return None


def _check_monotonic(ladder: list[dict]) -> dict:
    """Check if probabilities decrease as numeric values increase."""
    violations = 0
    for i in range(1, len(ladder)):
        if ladder[i]["market_prob"] > ladder[i - 1]["market_prob"] + 0.01:
            violations += 1
    return {
        "ok": violations == 0,
        "violations": violations,
        "penalty": _clamp(violations * 0.08, 0, 0.25),
    }


def _local_gap_score(ladder: list[dict], i: int) -> float:
    """Score local gap anomaly between adjacent outcomes."""
    if i == 0 or i == len(ladder) - 1:
        return 0
    left = ladder[i - 1]["market_prob"]
    mid = ladder[i]["market_prob"]
    right = ladder[i + 1]["market_prob"]
    gap_left = left - mid
    gap_right = mid - right
    diff = abs(gap_left - gap_right)
    return _clamp(diff, 0, 0.2)


def _smoothness_score(ladder: list[dict], i: int) -> float:
    """Score curvature (second derivative) at outcome i."""
    if i == 0 or i == len(ladder) - 1:
        return 0
    p_prev = ladder[i - 1]["market_prob"]
    p_mid = ladder[i]["market_prob"]
    p_next = ladder[i + 1]["market_prob"]
    curvature = p_prev - 2 * p_mid + p_next
    return _clamp(abs(curvature), 0, 0.2)


def _relative_value_score(ladder: list[dict], i: int) -> float:
    """Score deviation from interpolated neighbor expectation."""
    if i == 0 or i == len(ladder) - 1:
        return 0
    expected = (ladder[i - 1]["market_prob"] + ladder[i + 1]["market_prob"]) / 2
    actual = ladder[i]["market_prob"]
    diff = expected - actual  # positive = underpriced
    return _clamp(diff, -0.2, 0.2)


def _compute_structure_edge(local_gap: float, smoothness: float,
                            relative_value: float, monotonic_penalty: float) -> float:
    """Combine scores into final structure edge."""
    score = (
        local_gap * 0.30
        + smoothness * 0.20
        + relative_value * 0.50
        - monotonic_penalty
    )
    return _clamp(score, -0.12, 0.12)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
