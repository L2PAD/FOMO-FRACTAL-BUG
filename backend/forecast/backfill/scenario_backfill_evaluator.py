"""
Block 3.8 — 30D Scenario Backfill Evaluator
=============================================
Proves (or disproves) that scenarios are better than single-point forecast.

Compares:
  v4.2.1 baseline (single direction + confidence)
  vs
  v4.4.0 scenario engine (3 weighted scenarios with ranges)

Metrics:
  1. Coverage: >= 70% of actual moves fall within at least one scenario range
  2. Direction signal: dominant scenario vs real direction
  3. Range usefulness: spread-to-move ratio
  4. Decision improvement: PnL and catastrophic error comparison
  5. Confidence calibration: high_confidence really better?
"""

import os
import json
from datetime import datetime, timedelta

from pymongo import MongoClient

from forecast.price_provider import get_price_series
from forecast.backfill.historical_snapshot_builder import build_snapshot
from forecast.backfill.replay_runner import run_dual_replay
from forecast.scenario.scenario_assembler import build_scenarios
from forecast.scenario.scenario_evaluator import evaluate_scenario_set, evaluate_single


def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def run_30d_scenario_backfill(asset: str = "BTC") -> dict:
    """
    Full 30D scenario backfill.
    For each historical date, generate scenarios and compare with actual 30D outcome.
    """
    print(f"[30D Backfill] Starting scenario evaluation for {asset}")

    # Get price series
    prices = get_price_series(asset, "2024-01-01", "2027-01-01")
    all_dates = sorted(prices.keys())

    if not all_dates:
        return {"ok": False, "error": "No price data"}

    latest = datetime.strptime(all_dates[-1], "%Y-%m-%d")

    # Build evaluation window: need 30D of forward data for each date
    # Start from 120 days ago, end 30 days before latest
    end_date = (latest - timedelta(days=30)).strftime("%Y-%m-%d")
    start_date = (latest - timedelta(days=150)).strftime("%Y-%m-%d")

    print(f"[30D Backfill] Window: {start_date} → {end_date}")
    print(f"[30D Backfill] Latest price date: {all_dates[-1]}")

    # Build replay dates (every 3 days for adequate coverage)
    eval_dates = []
    d = datetime.strptime(start_date, "%Y-%m-%d")
    end_d = datetime.strptime(end_date, "%Y-%m-%d")
    while d <= end_d:
        ds = d.strftime("%Y-%m-%d")
        if ds in prices:
            eval_dates.append(ds)
        d += timedelta(days=3)

    print(f"[30D Backfill] {len(eval_dates)} evaluation dates")

    cases = []
    errors = 0

    for i, as_of in enumerate(eval_dates):
        try:
            case = _process_single_date(asset, as_of, prices, all_dates)
            if case:
                cases.append(case)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"[30D Backfill] Error at {as_of}: {e}")

        if (i + 1) % 10 == 0:
            print(f"[30D Backfill] Processed {i + 1}/{len(eval_dates)} ({len(cases)} valid)")

    print(f"[30D Backfill] Total: {len(cases)} valid cases, {errors} errors")

    if not cases:
        return {"ok": False, "error": "No valid cases generated"}

    # ── Evaluate scenarios ──
    scenario_eval = evaluate_scenario_set([
        {"scenarios": c["scenarios"], "real_move_pct": c["real_move_pct"]}
        for c in cases
    ])

    # ── Baseline comparison ──
    baseline_stats = _compute_baseline_comparison(cases)

    # ── Decision improvement ──
    decision_improvement = _compute_decision_improvement(cases)

    # ── Catastrophic errors ──
    catastrophic = _compute_catastrophic_analysis(cases)

    report = {
        "ok": True,
        "n_cases": len(cases),
        "n_errors": errors,
        "window": {"start": start_date, "end": end_date},
        "scenario_evaluation": scenario_eval,
        "baseline_comparison": baseline_stats,
        "decision_improvement": decision_improvement,
        "catastrophic_analysis": catastrophic,
    }

    return report


def _process_single_date(asset: str, as_of: str, prices: dict, all_dates: list) -> dict | None:
    """Process a single date: build snapshot, run replay, generate scenarios, get outcome."""
    # Build snapshot
    snapshot = build_snapshot(asset, as_of, "30D", prices)
    if not snapshot:
        return None

    # Get actual 30D outcome
    entry_price = snapshot["features"]["price"]
    outcome_date = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")

    # Find closest available date to outcome_date
    outcome_price = None
    for offset in range(0, 5):
        check_date = (datetime.strptime(outcome_date, "%Y-%m-%d") + timedelta(days=offset)).strftime("%Y-%m-%d")
        if check_date in prices:
            outcome_price = prices[check_date]
            break
        check_date = (datetime.strptime(outcome_date, "%Y-%m-%d") - timedelta(days=offset)).strftime("%Y-%m-%d")
        if check_date in prices:
            outcome_price = prices[check_date]
            break

    if outcome_price is None:
        return None

    real_move_pct = ((outcome_price - entry_price) / entry_price) * 100
    real_direction = "UP" if real_move_pct > 0 else "DOWN"

    # Run baseline replay (v4.2.0 single forecast)
    replay = run_dual_replay(snapshot, target_version="v4.3.0")

    baseline_direction = replay["structure"]["direction"]
    baseline_correct = _direction_match(baseline_direction, real_direction)
    baseline_move_pct = replay["structure"]["move_pct"]

    # Extract data for scenario input
    features = snapshot["features"]
    baseline_data = snapshot["baseline"]
    regime = snapshot["regime"]

    # Build scenario input from available data
    multiscale_meta = replay.get("multiscale_meta", {})
    regime_meta = multiscale_meta.get("regime")
    context_meta = multiscale_meta.get("context")

    structure_bias = 0.0
    struct_feats = replay.get("structure_features", {})
    if isinstance(struct_feats, dict):
        structure_bias = struct_feats.get("structure_bias_score", 0.0)

    scenario_input = {
        "momentum": features["momentum"],
        "volatility": features["volatility"],
        "ret_7d": features["ret_7d"],
        "ret_14d": features["ret_14d"],
        "median_return": baseline_data.get("medianReturn", 0.0),
        "std_return": baseline_data.get("stdReturn", 0.05),
        "p25_return": baseline_data.get("p25Return", -0.04),
        "p75_return": baseline_data.get("p75Return", 0.06),
        "mean_return": baseline_data.get("meanReturn", 0.0),
        "structure_bias": structure_bias,
        "mode": multiscale_meta.get("mode", "mixed_range"),
        "regime_probs": regime_meta.get("probabilities") if regime_meta else None,
        "dominant_regime": (regime_meta.get("dominant_regime") if regime_meta else regime).lower(),
        "regime_entropy": regime_meta.get("regime_entropy", 0.5) if regime_meta else 0.5,
        "decision_uncertainty": (
            regime_meta.get("adjustments", {}).get("decision_uncertainty", 0.5)
            if regime_meta and regime_meta.get("adjustments") else 0.5
        ),
        "context_phase": context_meta.get("phase") if context_meta else None,
    }

    # Generate scenarios
    scenario_set = build_scenarios(scenario_input)

    return {
        "as_of": as_of,
        "entry_price": round(entry_price, 2),
        "outcome_price": round(outcome_price, 2),
        "real_move_pct": round(real_move_pct, 2),
        "real_direction": real_direction,
        "scenarios": scenario_set,
        "baseline": {
            "direction": baseline_direction,
            "correct": baseline_correct,
            "move_pct": baseline_move_pct,
        },
    }


def _direction_match(predicted: str, actual: str) -> bool:
    """Check direction match (predicted = STRONG_BULL/MILD_BULL/etc, actual = UP/DOWN)."""
    if actual == "UP":
        return predicted in ("STRONG_BULL", "MILD_BULL")
    elif actual == "DOWN":
        return predicted in ("STRONG_BEAR", "MILD_BEAR")
    return predicted == "NEUTRAL"


def _compute_baseline_comparison(cases: list) -> dict:
    """Compare baseline single-forecast vs scenario dominant direction."""
    n = len(cases)
    baseline_correct = sum(1 for c in cases if c["baseline"]["correct"])
    dominant_correct = 0

    for c in cases:
        dominant = c["scenarios"]["dominant"]
        dom_scenario = next(s for s in c["scenarios"]["scenarios"] if s["type"] == dominant)
        dom_dir = "UP" if dom_scenario["expected_move"] > 0 else "DOWN"
        if dom_dir == c["real_direction"]:
            dominant_correct += 1

    return {
        "n": n,
        "baseline_direction_accuracy": round(baseline_correct / n, 4),
        "scenario_dominant_accuracy": round(dominant_correct / n, 4),
        "improvement_pp": round((dominant_correct - baseline_correct) / n * 100, 2),
    }


def _compute_decision_improvement(cases: list) -> dict:
    """Compute PnL and decision quality improvement."""
    n = len(cases)

    # Baseline PnL: bet ±1 unit based on direction
    baseline_pnl = 0
    scenario_pnl = 0

    for c in cases:
        real_move = c["real_move_pct"]

        # Baseline: binary bet
        base_dir = c["baseline"]["direction"]
        if base_dir in ("STRONG_BULL", "MILD_BULL"):
            baseline_pnl += real_move
        elif base_dir in ("STRONG_BEAR", "MILD_BEAR"):
            baseline_pnl -= real_move
        # NEUTRAL: 0

        # Scenario: probability-weighted direction bet
        # Size proportional to dominant scenario probability
        scenarios = c["scenarios"]["scenarios"]
        dominant = c["scenarios"]["dominant"]
        dom_s = next(s for s in scenarios if s["type"] == dominant)
        dom_prob = dom_s["probability"]

        if dom_s["expected_move"] > 0:
            scenario_pnl += real_move * dom_prob
        else:
            scenario_pnl -= real_move * dom_prob

    return {
        "baseline_pnl": round(baseline_pnl, 2),
        "scenario_pnl": round(scenario_pnl, 2),
        "pnl_delta": round(scenario_pnl - baseline_pnl, 2),
        "baseline_avg_pnl": round(baseline_pnl / n, 4),
        "scenario_avg_pnl": round(scenario_pnl / n, 4),
    }


def _compute_catastrophic_analysis(cases: list) -> dict:
    """Analyze catastrophic errors: large wrong bets."""
    n = len(cases)
    threshold = 5.0  # 5% = catastrophic threshold for 30D

    baseline_catastrophic = 0
    scenario_catastrophic = 0

    for c in cases:
        real_move = c["real_move_pct"]
        real_dir = c["real_direction"]

        # Baseline catastrophic: wrong direction AND big move
        base_dir = c["baseline"]["direction"]
        base_pred_dir = "UP" if base_dir in ("STRONG_BULL", "MILD_BULL") else "DOWN"
        if base_pred_dir != real_dir and abs(real_move) > threshold:
            baseline_catastrophic += 1

        # Scenario catastrophic: dominant wrong AND big move
        dominant = c["scenarios"]["dominant"]
        dom_s = next(s for s in c["scenarios"]["scenarios"] if s["type"] == dominant)
        dom_pred_dir = "UP" if dom_s["expected_move"] > 0 else "DOWN"
        if dom_pred_dir != real_dir and abs(real_move) > threshold:
            scenario_catastrophic += 1

    return {
        "threshold_pct": threshold,
        "baseline_catastrophic": baseline_catastrophic,
        "scenario_catastrophic": scenario_catastrophic,
        "baseline_rate": round(baseline_catastrophic / n, 4),
        "scenario_rate": round(scenario_catastrophic / n, 4),
        "improvement": baseline_catastrophic - scenario_catastrophic,
    }


if __name__ == "__main__":
    result = run_30d_scenario_backfill("BTC")
    print("\n" + "=" * 70)
    print("BLOCK 3.8 — 30D SCENARIO BACKFILL REPORT")
    print("=" * 70)
    print(json.dumps(result, indent=2))
