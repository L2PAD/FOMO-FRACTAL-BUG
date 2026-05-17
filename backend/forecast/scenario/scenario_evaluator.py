"""
Scenario Evaluator
===================
Evaluates scenario usefulness against real outcomes.

NOT accuracy-focused. Measures DECISION USEFULNESS:
  A. Coverage quality — at least 1 scenario hit the actual move
  B. Direction signal quality — dominant scenario vs real direction
  C. Range usefulness — range width vs actual move magnitude
  D. Confidence calibration — high_confidence cases actually better?

Input: list of evaluated cases, each with:
  - scenarios (output from scenario_assembler)
  - real_move_pct (actual price change %)
  - real_direction ("UP" / "DOWN")
"""

from forecast.scenario.scenario_types import SCENARIO_NAMES


def evaluate_scenario_set(cases: list[dict]) -> dict:
    """
    Evaluate a batch of scenario predictions against real outcomes.

    Each case must have:
      - scenarios: ScenarioSet from build_scenarios()
      - real_move_pct: float (actual 30D move in %)
    """
    n = len(cases)
    if n == 0:
        return {"n": 0, "error": "no cases"}

    # ── A. Coverage Quality ──
    # Did at least one scenario range contain the actual move?
    coverage_hits = 0
    per_scenario_hits = {s: 0 for s in SCENARIO_NAMES}
    best_scenario_match = {s: 0 for s in SCENARIO_NAMES}

    # ── B. Direction Signal Quality ──
    # Did the dominant scenario predict the correct direction?
    dominant_dir_correct = 0
    weighted_dir_correct = 0.0

    # ── C. Range Usefulness ──
    # Is the total spread useful (not too wide, not too narrow)?
    range_widths = []
    actual_moves = []
    within_base_count = 0

    # ── D. Confidence Calibration ──
    by_tag = {}

    for case in cases:
        ss = case["scenarios"]
        real_move = case["real_move_pct"]
        scenarios = ss["scenarios"]
        dominant = ss["dominant"]
        tag = ss["confidence_tag"]
        real_dir = "UP" if real_move > 0 else "DOWN"

        # A. Coverage: check each scenario range
        any_hit = False
        for s in scenarios:
            lo, hi = s["range"]
            if lo <= real_move <= hi:
                per_scenario_hits[s["type"]] += 1
                any_hit = True
            # Track which scenario center was closest to actual
            dist = abs(s["expected_move"] - real_move)
            if dist == min(abs(sc["expected_move"] - real_move) for sc in scenarios):
                best_scenario_match[s["type"]] += 1
        if any_hit:
            coverage_hits += 1

        # B. Direction signal
        dominant_scenario = next(s for s in scenarios if s["type"] == dominant)
        predicted_dir = "UP" if dominant_scenario["expected_move"] > 0 else "DOWN"
        if predicted_dir == real_dir:
            dominant_dir_correct += 1

        # Weighted direction: sum of prob * (correct direction)
        for s in scenarios:
            s_dir = "UP" if s["expected_move"] > 0 else "DOWN"
            if s_dir == real_dir:
                weighted_dir_correct += s["probability"]

        # C. Range usefulness
        range_widths.append(ss["spread"])
        actual_moves.append(abs(real_move))
        # Check if actual move falls within base scenario
        base_s = next(s for s in scenarios if s["type"] == "base")
        if base_s["range"][0] <= real_move <= base_s["range"][1]:
            within_base_count += 1

        # D. Confidence calibration
        if tag not in by_tag:
            by_tag[tag] = {"coverage": 0, "dir_correct": 0, "total": 0}
        by_tag[tag]["total"] += 1
        if any_hit:
            by_tag[tag]["coverage"] += 1
        if predicted_dir == real_dir:
            by_tag[tag]["dir_correct"] += 1

    # ── Aggregate Metrics ──
    avg_actual_move = sum(actual_moves) / n if n > 0 else 0
    avg_spread = sum(range_widths) / n if n > 0 else 0

    result = {
        "n": n,
        "coverage": {
            "total_hit_rate": round(coverage_hits / n, 4),
            "per_scenario_hits": per_scenario_hits,
            "best_match_distribution": best_scenario_match,
            "target": ">= 0.70",
        },
        "direction_signal": {
            "dominant_direction_accuracy": round(dominant_dir_correct / n, 4),
            "weighted_direction_score": round(weighted_dir_correct / n, 4),
        },
        "range_usefulness": {
            "avg_spread_pct": round(avg_spread, 2),
            "avg_actual_move_pct": round(avg_actual_move, 2),
            "spread_to_move_ratio": round(avg_spread / max(avg_actual_move, 0.1), 2),
            "base_scenario_hit_rate": round(within_base_count / n, 4),
        },
        "confidence_calibration": {},
    }

    for tag, data in by_tag.items():
        t = data["total"]
        result["confidence_calibration"][tag] = {
            "count": t,
            "coverage_rate": round(data["coverage"] / t, 4) if t > 0 else 0,
            "direction_accuracy": round(data["dir_correct"] / t, 4) if t > 0 else 0,
        }

    return result


def evaluate_single(scenario_set: dict, real_move_pct: float) -> dict:
    """
    Evaluate a single scenario prediction.
    Returns per-case metrics for inspection.
    """
    scenarios = scenario_set["scenarios"]
    dominant = scenario_set["dominant"]
    tag = scenario_set["confidence_tag"]
    real_dir = "UP" if real_move_pct > 0 else "DOWN"

    hits = []
    closest = None
    closest_dist = float("inf")

    for s in scenarios:
        lo, hi = s["range"]
        hit = lo <= real_move_pct <= hi
        dist = abs(s["expected_move"] - real_move_pct)
        hits.append({
            "type": s["type"],
            "hit": hit,
            "distance_to_center": round(dist, 2),
            "probability": s["probability"],
        })
        if dist < closest_dist:
            closest_dist = dist
            closest = s["type"]

    dominant_s = next(s for s in scenarios if s["type"] == dominant)
    dominant_dir = "UP" if dominant_s["expected_move"] > 0 else "DOWN"

    return {
        "real_move_pct": round(real_move_pct, 2),
        "real_direction": real_dir,
        "any_hit": any(h["hit"] for h in hits),
        "hits": hits,
        "closest_scenario": closest,
        "dominant": dominant,
        "dominant_direction_correct": dominant_dir == real_dir,
        "confidence_tag": tag,
    }
