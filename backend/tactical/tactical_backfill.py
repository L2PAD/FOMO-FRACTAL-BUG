"""
Tactical Backfill Evaluator
==============================
Block X — Task X.6

Validates the Tactical Layer against historical exchange_observations.
This is NOT a price prediction backfill — it evaluates "decision usefulness":
  - Does bearish bias precede a negative short-horizon move?
  - Does "wait" advice correspond to high-vol / adverse periods?
  - Is the false positive rate controlled?
  - Does the layer improve PnL under advisory simulation?

Methodology:
  1. Sample observations every ~4h from BTCUSDT (avoid redundant snapshots)
  2. For each, run through the full tactical pipeline
  3. Find the observation ~24h forward to measure actual outcome
  4. Compute KPIs: bias accuracy, PnL delta, avoid-loss usefulness, noise
"""

import os
import json
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from tactical.tactical_signal_builder import build_tactical_signals
from tactical.tactical_fusion_engine import fuse_tactical_signals
from tactical.tactical_advisor import build_tactical_advice
from exchange.normalization.asset_normalizer import normalize_features


def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    return MongoClient(mongo_url)[db_name]


def _build_snapshot_from_obs(obs: dict, funding: dict | None, asset: str = "BTC") -> dict:
    """Convert a raw exchange_observation doc into a MicrostructureSnapshot.
    Block 7.3: adds *_norm fields via asset normalization."""
    of = obs.get("orderFlow") or {}
    liq = obs.get("liquidations") or {}
    vol = obs.get("volume") or {}
    oi = obs.get("openInterest") or {}
    market = obs.get("market") or {}
    fund = funding or {}

    raw = {
        "imbalance": of.get("imbalance", 0.0),
        "dominance": of.get("dominance", 0.5),
        "aggressor_bias": of.get("aggressorBias", "NEUTRAL"),
        "long_liq_volume": liq.get("longVolume", 0),
        "short_liq_volume": liq.get("shortVolume", 0),
        "cascade_active": liq.get("cascadeActive", False),
        "cascade_direction": liq.get("cascadeDirection", ""),
        "cascade_phase": liq.get("cascadePhase") or "",
        "funding_score": fund.get("fundingScore", 0.0),
        "funding_trend": fund.get("fundingTrend", 0.0),
        "funding_label": fund.get("label", "NEUTRAL"),
        "absorption": of.get("absorption", False),
        "absorption_side": of.get("absorptionSide", ""),
        "volume_delta": vol.get("delta", 0),
        "oi_delta_pct": oi.get("deltaPct", 0),
        "uncertainty": 0.5,
        "regime": (obs.get("regime") or {}).get("type", "UNKNOWN"),
        "phase": None,
        "_price": market.get("price", 0),
        "_timestamp": obs.get("timestamp", 0),
    }

    # Block 7.3: add normalized features
    norm_input = {
        "imbalance": raw["imbalance"],
        "longVolume": raw["long_liq_volume"],
        "shortVolume": raw["short_liq_volume"],
        "funding_score": raw["funding_score"],
        "volatility": market.get("volatility", 0),
    }
    normed = normalize_features(norm_input, asset)

    raw["imbalance_norm"] = normed.get("imbalance_norm", 0)
    raw["liq_long_norm"] = normed.get("liq_long_norm", 0)
    raw["liq_short_norm"] = normed.get("liq_short_norm", 0)
    raw["funding_norm"] = normed.get("funding_norm", 0)
    raw["volatility_norm"] = normed.get("volatility_norm", 0)

    return raw


def _fetch_funding_at(db, symbol: str, ts: float) -> dict | None:
    """Get the closest funding context before a given timestamp."""
    doc = db["exchange_funding_context"].find_one(
        {"symbol": symbol, "ts": {"$lte": ts}},
        {"_id": 0},
        sort=[("ts", -1)],
    )
    return doc


def _sample_observations(db, symbol: str, interval_ms: int = 4 * 3600 * 1000) -> list:
    """
    Sample observations at ~4h intervals to avoid redundancy.
    Returns list of raw observation docs.
    """
    all_obs = list(
        db["exchange_observations"]
        .find({"symbol": symbol}, {"_id": 0})
        .sort("timestamp", 1)
    )

    if not all_obs:
        return []

    sampled = [all_obs[0]]
    last_ts = all_obs[0]["timestamp"]

    for obs in all_obs[1:]:
        if obs["timestamp"] - last_ts >= interval_ms:
            sampled.append(obs)
            last_ts = obs["timestamp"]

    return sampled


def _find_forward_price(all_obs: list, idx: int, horizon_ms: int = 24 * 3600 * 1000) -> float | None:
    """
    Find the observation closest to +horizon_ms from the current one.
    Returns the market price at that point, or None if no data.
    """
    target_ts = all_obs[idx]["timestamp"] + horizon_ms
    best = None
    best_diff = float("inf")

    # Search forward from current index
    for j in range(idx + 1, len(all_obs)):
        diff = abs(all_obs[j]["timestamp"] - target_ts)
        if diff < best_diff:
            best_diff = diff
            best = all_obs[j]
        if all_obs[j]["timestamp"] > target_ts + horizon_ms:
            break  # too far, stop

    # Accept if within 6h tolerance
    if best and best_diff < 6 * 3600 * 1000:
        return (best.get("market") or {}).get("price")

    return None


def run_tactical_backfill(asset: str = "BTC") -> dict:
    """
    Full tactical backfill evaluation.

    Pipeline:
      1. Sample observations every ~4h
      2. For each, build snapshot → run tactical pipeline → measure 24h outcome
      3. Compute aggregate KPIs
    """
    print(f"[Tactical Backfill] Starting for {asset}")
    db = _get_db()
    symbol = f"{asset}USDT"

    # Get all observations (sorted)
    all_obs = list(
        db["exchange_observations"]
        .find({"symbol": symbol}, {"_id": 0})
        .sort("timestamp", 1)
    )
    print(f"[Tactical Backfill] Total observations: {len(all_obs)}")

    if not all_obs:
        return {"ok": False, "error": "No observations found"}

    # Sample at ~4h intervals
    interval_ms = 4 * 3600 * 1000
    sampled = []
    last_ts = 0
    sampled_indices = []

    for i, obs in enumerate(all_obs):
        if obs["timestamp"] - last_ts >= interval_ms:
            sampled.append(obs)
            sampled_indices.append(i)
            last_ts = obs["timestamp"]

    print(f"[Tactical Backfill] Sampled: {len(sampled)} (every ~4h)")

    cases = []
    skipped_no_price = 0
    skipped_no_forward = 0

    for si, (obs, obs_idx) in enumerate(zip(sampled, sampled_indices)):
        entry_price = (obs.get("market") or {}).get("price")
        if not entry_price or entry_price <= 0:
            skipped_no_price += 1
            continue

        # Find price 24h forward
        forward_price = _find_forward_price(all_obs, obs_idx, horizon_ms=24 * 3600 * 1000)
        if not forward_price:
            skipped_no_forward += 1
            continue

        # Build snapshot with funding context
        funding = _fetch_funding_at(db, symbol, obs["timestamp"])
        snap = _build_snapshot_from_obs(obs, funding, asset)

        # Run tactical pipeline (Block 7.4: asset-aware thresholds)
        signals = build_tactical_signals(snap, asset)
        fusion = fuse_tactical_signals(signals)
        advice = build_tactical_advice(fusion, snap)

        # Calculate outcome
        move_pct = ((forward_price - entry_price) / entry_price) * 100
        real_direction = "up" if move_pct > 0 else "down"

        cases.append({
            "timestamp": obs["timestamp"],
            "entry_price": round(entry_price, 2),
            "forward_price": round(forward_price, 2),
            "move_pct": round(move_pct, 4),
            "real_direction": real_direction,
            "bias": fusion["bias"],
            "score": fusion["score"],
            "signal_strength": fusion["signal_strength"],
            "active_signals": fusion["active_signals"],
            "execution_advice": advice["executionAdvice"],
            "trade_quality": advice["tradeQuality"],
            "volatility_expectation": advice["volatilityExpectation"],
            "reason_flags": advice["reasonFlags"],
        })

    print(f"[Tactical Backfill] Valid cases: {len(cases)}")
    print(f"[Tactical Backfill] Skipped (no price): {skipped_no_price}, (no forward): {skipped_no_forward}")

    if not cases:
        return {"ok": False, "error": "No valid cases with forward price data"}

    # ── Compute KPIs ──
    kpi = _compute_kpis(cases)

    return {
        "ok": True,
        "n_cases": len(cases),
        "skipped": {
            "no_entry_price": skipped_no_price,
            "no_forward_price": skipped_no_forward,
        },
        "kpi": kpi,
        "sample_cases": cases[:5] + cases[-5:] if len(cases) > 10 else cases,
    }


def _compute_kpis(cases: list) -> dict:
    """Compute all tactical layer KPIs."""
    n = len(cases)

    # ── 1. Bias distribution ──
    bias_dist = defaultdict(int)
    for c in cases:
        bias_dist[c["bias"]] += 1

    bias_pct = {k: round(v / n * 100, 1) for k, v in bias_dist.items()}

    # ── 2. Bias accuracy ──
    # When bias is directional, does actual move match?
    directional_cases = [c for c in cases if c["bias"] != "neutral"]
    if directional_cases:
        bias_correct = sum(
            1 for c in directional_cases
            if (c["bias"] == "bearish" and c["real_direction"] == "down")
            or (c["bias"] == "bullish" and c["real_direction"] == "up")
        )
        bias_accuracy = round(bias_correct / len(directional_cases) * 100, 1)
    else:
        bias_correct = 0
        bias_accuracy = 0.0

    # ── 3. Activation rate ──
    activation_rate = round(len(directional_cases) / n * 100, 1)

    # ── 4. PnL simulation ──
    # Strategy: follow tactical bias when directional, flat when neutral
    # Size = signal_strength (0-1)
    tactical_pnl = 0.0
    baseline_pnl = 0.0  # Always long (simple benchmark)

    for c in cases:
        move = c["move_pct"]
        baseline_pnl += move  # always long

        if c["bias"] == "bearish":
            # Bearish: reduce/avoid. Simulated as -size * move (short bias)
            size = c["signal_strength"]
            tactical_pnl -= move * size
        elif c["bias"] == "bullish":
            # Bullish: size with signal
            size = c["signal_strength"]
            tactical_pnl += move * size
        # Neutral: flat, 0 contribution

    # ── 5. Execution advice analysis ──
    advice_dist = defaultdict(int)
    for c in cases:
        advice_dist[c["execution_advice"]] += 1

    advice_pct = {k: round(v / n * 100, 1) for k, v in advice_dist.items()}

    # When advice = "wait", "avoid_aggressive", or "reduced", what was the avg abs move?
    # (Should be higher = correctly flagging dangerous periods)
    caution_cases = [c for c in cases if c["execution_advice"] in ("wait", "avoid_aggressive", "reduced")]
    normal_cases = [c for c in cases if c["execution_advice"] == "normal"]

    avg_abs_move_caution = (
        round(sum(abs(c["move_pct"]) for c in caution_cases) / len(caution_cases), 4)
        if caution_cases else 0.0
    )
    avg_abs_move_normal = (
        round(sum(abs(c["move_pct"]) for c in normal_cases) / len(normal_cases), 4)
        if normal_cases else 0.0
    )

    # ── 6. Bearish bias → negative move analysis ──
    bearish_cases = [c for c in cases if c["bias"] == "bearish"]
    bullish_cases = [c for c in cases if c["bias"] == "bullish"]

    avg_move_when_bearish = (
        round(sum(c["move_pct"] for c in bearish_cases) / len(bearish_cases), 4)
        if bearish_cases else 0.0
    )
    avg_move_when_bullish = (
        round(sum(c["move_pct"] for c in bullish_cases) / len(bullish_cases), 4)
        if bullish_cases else 0.0
    )
    avg_move_when_neutral = (
        round(
            sum(c["move_pct"] for c in cases if c["bias"] == "neutral")
            / max(1, sum(1 for c in cases if c["bias"] == "neutral")),
            4,
        )
    )

    # ── 7. Catastrophic avoidance ──
    # Cases where |move| > 3% and advice was "wait"/"avoid_aggressive"
    big_moves = [c for c in cases if abs(c["move_pct"]) > 3.0]
    big_moves_cautioned = [
        c for c in big_moves
        if c["execution_advice"] in ("wait", "avoid_aggressive", "reduced")
    ]
    catastrophic_catch_rate = (
        round(len(big_moves_cautioned) / len(big_moves) * 100, 1)
        if big_moves else 0.0
    )

    # ── 8. Signal frequency ──
    signal_freq = defaultdict(int)
    for c in cases:
        for sig in c["active_signals"]:
            signal_freq[sig] += 1
    signal_pct = {k: round(v / n * 100, 1) for k, v in sorted(signal_freq.items(), key=lambda x: -x[1])}

    return {
        "n_cases": n,
        "bias_distribution": bias_pct,
        "activation_rate_pct": activation_rate,
        "directional_cases": len(directional_cases),
        "bias_accuracy_pct": bias_accuracy,
        "bias_correct": bias_correct,
        "avg_move_when_bearish": avg_move_when_bearish,
        "avg_move_when_bullish": avg_move_when_bullish,
        "avg_move_when_neutral": avg_move_when_neutral,
        "pnl": {
            "tactical": round(tactical_pnl, 2),
            "baseline_always_long": round(baseline_pnl, 2),
            "delta": round(tactical_pnl - baseline_pnl, 2),
            "tactical_avg": round(tactical_pnl / n, 4),
            "baseline_avg": round(baseline_pnl / n, 4),
        },
        "execution_advice_distribution": advice_pct,
        "avg_abs_move_caution": avg_abs_move_caution,
        "avg_abs_move_normal": avg_abs_move_normal,
        "caution_vs_normal_ratio": (
            round(avg_abs_move_caution / max(avg_abs_move_normal, 0.0001), 2)
        ),
        "big_moves_total": len(big_moves),
        "big_moves_cautioned": len(big_moves_cautioned),
        "catastrophic_catch_rate_pct": catastrophic_catch_rate,
        "signal_frequency": signal_pct,
    }


if __name__ == "__main__":
    result = run_tactical_backfill("BTC")
    print("\n" + "=" * 70)
    print("BLOCK X — TACTICAL BACKFILL REPORT")
    print("=" * 70)
    print(json.dumps(result, indent=2, default=str))
