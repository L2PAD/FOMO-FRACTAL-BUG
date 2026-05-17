"""
Forecast Generator v4.1 — Emergency Recovery + Structure Intelligence V2
=========================================================================
Changes from v4.0:
  1. 5-state direction classifier (STRONG_BULL → STRONG_BEAR)
  2. No forced-neutral throttle — degradation is soft only
  3. Suppression stack capped (max 25% score, 30% move, 35% confidence)
  4. Score determines direction BEFORE confidence is calculated
  5. Blended baselines (65% recent + 35% long)
  6. Calibrated confidence (bucket mapping per horizon)
  7. Full audit payload per forecast
  8. TRANSITION shrinkage raised 0.6 → 0.82
  9. Structure Intelligence hook: bias modifier from price structure

KEY RULE: No penalty or degradation rule may force NEUTRAL
if the raw directional score fell outside the neutral zone.
"""

import hashlib
import math
import uuid
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

from forecast import ForecastRecord, Horizon, HORIZON_DAYS
from forecast.price_provider import get_current_price, get_price_series
from forecast.v41_config import (
    classify_direction,
    get_active_mild_threshold,
    REGIME_SHRINKAGE,
    MAX_SCORE_REDUCTION,
    MAX_MOVE_REDUCTION,
    MAX_CONFIDENCE_REDUCTION,
    DEGRADATION_CONFIG,
    BASELINE_BLEND,
)
from exchange.calibration.confidence_calibrator import (
    calibrate_confidence as _calibrate_direction,
    calibrate_confidence_target as _calibrate_target,
    get_calibration_info,
)
from forecast.structure.extractor import StructureFeatureExtractor
from forecast.structure.optimizer import StructureWeightOptimizer
from forecast.structure.shadow import record_shadow
from forecast.structure.multi_scale_extractor import extract_multiscale
from forecast.structure.pullback_detector import detect_mode
from forecast.structure.major_minor_fusion import fuse as fuse_major_minor, apply_multiscale_guards
from forecast.structure.direction_override_gate import DirectionOverrideGate
from forecast.context.context_feature_builder import build_context_features
from forecast.context.context_phase_classifier import classify_phase
from forecast.context.context_adjustment_engine import apply_context
from forecast.context.context_audit_builder import build_context_audit
from forecast.regime.regime_feature_builder import build_regime_features
from forecast.regime.regime_probability_engine import compute_regime_probabilities
from forecast.regime.regime_postprocessor import postprocess_regime
from forecast.adapters.exchange_signal_adapter import build_exchange_signal, apply_exchange_bias
from forecast.regime.regime_adjustment_engine import apply_regime_adjustments
from forecast.regime.regime_audit_builder import build_regime_audit
from forecast.scenario.scenario_assembler import build_scenarios
from forecast.scenario.engine_v2 import ScenarioEngineV2, TruthInputs, ScenarioCalibratorAdapter
from forecast.decision.contracts import DecisionInputs
from forecast.decision.engine import DecisionLayerV1
from forecast.decision.scenario_proxy import derive_scenario_probs
from forecast.decision.drr_engine import DRREngine, DRRInputs, compute_bearish_structure_v2
from forecast.decision.unified_structure import UnifiedStructureEngine, StructureInputs
from forecast.decision.interaction_layer import InteractionLayerV1, InteractionInputs as _InteractionInputs
from forecast.decision.meta_calibration import (
    MetaCalibrationLayerV2,
    resolve_state_group,
)

# Singleton instances — created once, reused per forecast
_structure_extractor = StructureFeatureExtractor()
_structure_optimizer = StructureWeightOptimizer()
_override_gate = DirectionOverrideGate()
_scenario_calibrator = ScenarioCalibratorAdapter(horizon="30D", cache_ttl=3600)
_scenario_engine_v2 = ScenarioEngineV2(temperature=0.9, calibrator=_scenario_calibrator)
_decision_layer = DecisionLayerV1()
_drr_engine = DRREngine()
_structure_engine = UnifiedStructureEngine()
_interaction_layer = InteractionLayerV1()

# Feature flag: Structure V2 blending weight (0 = legacy only, 1 = V2 only)
STRUCTURE_V2_BLEND = 0.5

# Feature flags: Interaction Layer V1 (staged rollout)
INTERACTION_ENABLED = True           # Stage 1: shadow (compute + audit, no output impact)
INTERACTION_USE_CONFIDENCE = True    # Stage 2: apply confidence_modifier ← LIVE
INTERACTION_KILL_SWITCH = False      # Emergency: True = revert to calibrated_conf instantly
INTERACTION_USE_SCENARIO = False     # Stage 3: apply scenario reweighting
INTERACTION_USE_DECISION = False     # Stage 4: apply decision_bias_modifier

# Per-horizon confidence modifier scale (24H noisier → lower scale)
INTERACTION_CONF_SCALE = {
    "24H": 0.45,
    "7D": 0.60,
    "30D": 0.65,
}

# Pre-clip caps for interaction confidence modifier delta
INTERACTION_CONF_PRECLIP = (-0.15, 0.12)

# Feature flags: Meta-Calibration V2 (state-aware scaling)
META_V2_ENABLED = False              # Stage V2.1: shadow (compute + log)
META_V2_USE_CONFIDENCE = False       # Stage V2.2+: apply per-group scales
META_V2_BLEND_WITH_V1 = 0.5         # blending ratio (0 = V1 only, 1 = V2 only)


# ═══════════════════════════════════════════════════════
# Block 9: TruthInputs builder helpers
# ═══════════════════════════════════════════════════════

def _compute_regime_gap(regime_probs: dict | None) -> float:
    if not regime_probs:
        return 0.0
    sorted_probs = sorted(regime_probs.values(), reverse=True)
    return sorted_probs[0] - sorted_probs[1] if len(sorted_probs) >= 2 else 0.0


def _compute_bullish_structure(sf: dict | None) -> float:
    if not sf:
        return 0.5
    bias = sf.get("structure_bias_score", 0.0)
    trend = sf.get("structure_trend_score", 0.0)
    momentum = sf.get("structure_momentum_score", 0.0)
    return max(0.0, min(1.0, max(0, bias) * 0.5 + trend * 0.3 + max(0, momentum) * 0.2))


def _compute_bearish_structure(sf: dict | None, ctx: dict | None) -> float:
    """Legacy bearish structure (fallback when regime_v2 features unavailable)."""
    if not sf:
        return 0.5
    bias = sf.get("structure_bias_score", 0.0)
    reversal = sf.get("structure_reversal_risk", 0.0)
    exhaustion = sf.get("structure_exhaustion_score", 0.0)
    drawdown = ctx.get("drawdown_pressure", 0.0) if ctx else 0.0
    return max(0.0, min(1.0, max(0, -bias) * 0.4 + reversal * 0.25 + exhaustion * 0.20 + drawdown * 0.15))


def _compute_bearish_structure_drr(regime_feats: dict, regime_post: dict, base_bearish: float = 0.0) -> float:
    """DRR-powered bearish_structure. Uses regime_v2 features for accurate downside sensing."""
    drr_inp = DRRInputs(
        trend_strength=regime_feats.get("trend_strength", 0.5),
        trend_persistence=regime_feats.get("trend_persistence", 0.5),
        exhaustion=regime_feats.get("exhaustion", 0.0),
        reversal_risk=regime_feats.get("reversal_risk", 0.0),
        drawdown_pressure=regime_feats.get("drawdown_pressure", 0.0),
        structure_alignment=regime_feats.get("structure_alignment", 0.5),
        volatility_expansion=regime_feats.get("volatility_expansion", 0.0),
        dominant_regime=regime_post.get("dominant_regime", "range"),
        breakdown_prob=regime_post.get("probabilities", {}).get("breakdown", 0.05),
    )
    drr_out = _drr_engine.compute(drr_inp)
    return compute_bearish_structure_v2(
        drr=drr_out,
        negative_context=regime_feats.get("drawdown_pressure", 0.0),
        volatility_expansion=regime_feats.get("volatility_expansion", 0.0),
        structure_alignment=regime_feats.get("structure_alignment", 0.5),
        base_bearish=base_bearish,
    )


def _compute_range_state(sf: dict | None) -> float:
    if not sf:
        return 0.5
    compression = sf.get("structure_compression_score", 0.0)
    trend = sf.get("structure_trend_score", 0.0)
    return max(0.0, min(1.0, compression * 0.5 + (1 - trend) * 0.5))


def _get_db():
    import os
    try:
        from forecast.repo import _cfg
        c = _cfg()
        return MongoClient(c.mongo_url)[c.db_name]
    except RuntimeError:
        # Fallback: use environment directly
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
        db_name = os.environ.get("DB_NAME", "intelligence_engine")
        return MongoClient(mongo_url)[db_name]


# ═══════════════════════════════════════════════════════
# Feature Extraction (unchanged from v4)
# ═══════════════════════════════════════════════════════

def _compute_features(prices: dict[str, float], as_of_date: str) -> dict | None:
    sorted_dates = sorted(d for d in prices if d <= as_of_date)
    if len(sorted_dates) < 14:
        return None

    closes = [prices[d] for d in sorted_dates[-14:]]
    current = closes[-1]
    ret_1d = (closes[-1] - closes[-2]) / closes[-2]
    ret_7d = (closes[-1] - closes[-8]) / closes[-8] if len(closes) >= 8 else 0
    ret_14d = (closes[-1] - closes[0]) / closes[0]

    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    volatility = (sum(r**2 for r in daily_returns) / len(daily_returns)) ** 0.5

    momentum = ret_1d * 0.5 + ret_7d * 0.3 + ret_14d * 0.2

    features_hash = hashlib.sha256(
        f"{current:.2f}:{ret_1d:.6f}:{ret_7d:.6f}:{volatility:.6f}".encode()
    ).hexdigest()[:16]

    return {
        "price": current,
        "ret_1d": ret_1d,
        "ret_7d": ret_7d,
        "ret_14d": ret_14d,
        "volatility": volatility,
        "momentum": momentum,
        "features_hash": features_hash,
    }


# ═══════════════════════════════════════════════════════
# Regime Detection (unchanged, will be v5 rework)
# ═══════════════════════════════════════════════════════

def _compute_raw_regime(prices_dict: dict) -> str:
    dates = sorted(prices_dict.keys())
    if len(dates) < 14:
        return "TRANSITION"

    n = min(30, len(dates))
    prices = [prices_dict[d] for d in dates[-n:]]
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

    vol_30d = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * math.sqrt(365) if returns else 0
    ma_period = len(prices)
    ma = sum(prices) / ma_period
    ma_5ago = sum(prices[:-5]) / max(1, ma_period - 5) if ma_period > 5 else ma
    slope = (ma - ma_5ago) / ma_5ago if ma_5ago > 0 else 0
    max_7d = max(prices[-7:]) if len(prices) >= 7 else prices[-1]
    drawdown = (prices[-1] - max_7d) / max_7d if max_7d > 0 else 0

    if drawdown < -0.10 and vol_30d > 0.50:
        return "RISK_OFF"
    if abs(slope) > 0.002 and vol_30d <= 0.85:
        return "TREND"
    if vol_30d <= 0.45 and abs(slope) <= 0.002 and drawdown > -0.10:
        return "RANGE"
    return "TRANSITION"


def _apply_live_hysteresis(asset: str, horizon_key: str, raw_regime: str) -> tuple:
    db = _get_db()
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db["regime_signals"].update_one(
        {"asset": asset, "horizon": horizon_key, "date": bucket},
        {"$set": {"raw_regime": raw_regime, "ts": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    signals = list(db["regime_signals"].find(
        {"asset": asset, "horizon": horizon_key},
        {"_id": 0, "raw_regime": 1, "date": 1},
    ).sort("date", DESCENDING).limit(5))

    if len(signals) < 3:
        return raw_regime, 0.5

    last_3 = [s["raw_regime"] for s in signals[:3]]
    if len(set(last_3)) == 1:
        confirmed = last_3[0]
        last_5 = [s["raw_regime"] for s in signals[:5]]
        conf = 0.9 if len(set(last_5)) == 1 else 0.75
        return confirmed, conf

    prev = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon_key},
        {"_id": 0, "regime": 1, "regimeConfidence": 1},
        sort=[("ts", DESCENDING)],
    )
    if prev:
        return prev.get("regime", "TRANSITION"), prev.get("regimeConfidence", 0.5)
    return "TRANSITION", 0.5


# ═══════════════════════════════════════════════════════
# v4.1 NEW: Blended Baselines
# ═══════════════════════════════════════════════════════

def _get_blended_baseline(asset: str, horizon_key: str, regime: str) -> dict:
    """
    Compute blended baseline: 65% recent (60d) + 35% long-term.
    Falls back to long-only if recent sample is too small.
    """
    db = _get_db()
    cfg = BASELINE_BLEND

    # Long-term baseline from stored regime baselines
    baseline_doc = db["drift_regime_baselines"].find_one(
        {"regime": regime, "horizon": horizon_key},
        {"_id": 0, "baseline": 1},
    )
    long_bl = baseline_doc.get("baseline", {}) if baseline_doc else {}

    long_data = {
        "meanReturn": long_bl.get("mean_return", 0.0),
        "stdReturn": long_bl.get("std_return", 0.05),
        "maeMean": long_bl.get("mae_mean", 0.05),
        "dirHitMean": long_bl.get("dir_hit_mean", 0.5),
        "medianReturn": long_bl.get("median_return", 0.0),
        "p25Return": long_bl.get("p25_return", -0.05),
        "p75Return": long_bl.get("p75_return", 0.05),
        "sampleSize": long_bl.get("n", 0),
    }

    # Recent baseline from evaluated forecasts
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    recent_cutoff = now_ms - cfg["recent_window_days"] * 86_400_000

    recent_docs = list(db["exchange_forecasts"].find(
        {
            "asset": asset,
            "horizon": horizon_key,
            "evaluated": True,
            "outcome": {"$ne": None},
            "createdAt": {"$gte": recent_cutoff},
        },
        {"_id": 0, "outcome": 1, "direction": 1, "targetPrice": 1, "entryPrice": 1},
    ))

    if len(recent_docs) < cfg["min_recent_samples"]:
        # Try fallback window
        fallback_cutoff = now_ms - cfg["fallback_window_days"] * 86_400_000
        recent_docs = list(db["exchange_forecasts"].find(
            {
                "asset": asset,
                "horizon": horizon_key,
                "evaluated": True,
                "outcome": {"$ne": None},
                "createdAt": {"$gte": fallback_cutoff},
            },
            {"_id": 0, "outcome": 1, "direction": 1, "targetPrice": 1, "entryPrice": 1},
        ))

    if len(recent_docs) >= cfg["min_recent_samples"]:
        # Compute recent stats
        errors = []
        dir_hits = []
        returns = []

        for doc in recent_docs:
            outcome = doc.get("outcome", {})
            entry = doc.get("entryPrice", 0)
            target = doc.get("targetPrice", entry)
            real_price = outcome.get("realPrice") or outcome.get("actualPriceAtEval", 0)

            if entry > 0 and real_price and real_price > 0:
                r_real = (real_price / entry) - 1
                r_rule = (target / entry) - 1
                returns.append(r_real)
                errors.append(abs(r_real - r_rule))
                dir_match = (r_real > 0) == (r_rule > 0) if r_rule != 0 else False
                dir_hits.append(1 if dir_match else 0)

        if returns:
            import numpy as np
            recent_data = {
                "meanReturn": float(np.mean(returns)),
                "stdReturn": float(np.std(returns)) if len(returns) > 1 else 0.05,
                "maeMean": float(np.mean(errors)) if errors else 0.05,
                "dirHitMean": float(np.mean(dir_hits)) if dir_hits else 0.5,
                "medianReturn": float(np.median(returns)),
                "p25Return": float(np.percentile(returns, 25)),
                "p75Return": float(np.percentile(returns, 75)),
                "sampleSize": len(returns),
            }

            # Blend
            rw = cfg["recent_weight"]
            lw = cfg["long_weight"]
            blended = {}
            for key in ("meanReturn", "stdReturn", "maeMean", "dirHitMean", "medianReturn", "p25Return", "p75Return"):
                blended[key] = rw * recent_data[key] + lw * long_data[key]
            blended["sampleSize"] = recent_data["sampleSize"] + long_data["sampleSize"]
            blended["baselineSource"] = "blended"
            blended["recentSamples"] = recent_data["sampleSize"]
            return blended

    # Not enough recent data → use long only
    long_data["baselineSource"] = "long_only"
    long_data["recentSamples"] = 0
    return long_data


def _get_regime_data(asset: str, horizon_key: str, prices_dict: dict = None) -> dict:
    try:
        db = _get_db()

        if prices_dict:
            raw = _compute_raw_regime(prices_dict)
            regime, regime_conf = _apply_live_hysteresis(asset, horizon_key, raw)
        else:
            snap = db["drift_snapshots"].find_one(
                {"asset": asset, "horizon": horizon_key},
                {"_id": 0, "regime": 1, "regimeConfidence": 1},
                sort=[("ts", DESCENDING)],
            )
            regime = snap.get("regime", "TRANSITION") if snap else "TRANSITION"
            regime_conf = snap.get("regimeConfidence", 0.5) if snap else 0.5

        # v4.1: use blended baseline instead of only long-term
        baseline = _get_blended_baseline(asset, horizon_key, regime)

        return {
            "regime": regime,
            "regimeConfidence": regime_conf,
            "maeMean": baseline.get("maeMean", 0.05),
            "dirHitMean": baseline.get("dirHitMean", 0.5),
            "meanReturn": baseline.get("meanReturn", 0.0),
            "stdReturn": baseline.get("stdReturn", 0.05),
            "medianReturn": baseline.get("medianReturn", 0.0),
            "p25Return": baseline.get("p25Return", -0.05),
            "p75Return": baseline.get("p75Return", 0.05),
            "sampleSize": baseline.get("sampleSize", 0),
            "baselineSource": baseline.get("baselineSource", "unknown"),
            "recentSamples": baseline.get("recentSamples", 0),
        }
    except Exception:
        return {
            "regime": "TRANSITION",
            "regimeConfidence": 0.5,
            "maeMean": 0.05,
            "dirHitMean": 0.5,
            "meanReturn": 0.0,
            "stdReturn": 0.05,
            "medianReturn": 0.0,
            "p25Return": -0.05,
            "p75Return": 0.05,
            "sampleSize": 0,
            "baselineSource": "fallback",
            "recentSamples": 0,
        }


def _get_recent_performance(asset: str, horizon_key: str) -> dict:
    """Get rolling performance for soft degradation."""
    try:
        db = _get_db()
        recent = list(db["exchange_forecasts"].find(
            {"asset": asset, "horizon": horizon_key, "outcome": {"$ne": None}},
            {"_id": 0, "outcome": 1},
        ).sort("createdBucket", DESCENDING).limit(5))
        if not recent:
            return {"rollingWinRate": 0.5, "recentCount": 0}
        wins = sum(1 for r in recent if r.get("outcome", {}).get("label") == "TP")
        return {"rollingWinRate": wins / len(recent), "recentCount": len(recent)}
    except Exception:
        return {"rollingWinRate": 0.5, "recentCount": 0}


# ═══════════════════════════════════════════════════════
# v4.1: Soft Degradation (replaces forced-neutral throttle)
# ═══════════════════════════════════════════════════════

def _apply_soft_degradation(score: float, move: float, confidence_raw: float, perf: dict) -> tuple:
    """
    Apply soft penalties based on recent performance.
    NEVER forces NEUTRAL — only shrinks score/move/confidence.
    Returns (score, move, confidence, degraded, penalties_applied).
    """
    penalties = []
    score_factor = 1.0
    move_factor = 1.0
    conf_factor = 1.0
    degraded = False
    cfg = DEGRADATION_CONFIG

    win_rate = perf.get("rollingWinRate", 0.5)
    count = perf.get("recentCount", 0)

    # Heavy degradation
    if count >= cfg["heavy_min_samples"] and win_rate < cfg["heavy_threshold"]:
        score_factor *= cfg["heavy_score_factor"]
        move_factor *= cfg["heavy_move_factor"]
        conf_factor *= cfg["heavy_confidence_factor"]
        degraded = True
        penalties.append(f"heavy_degrad(wr={win_rate:.2f},n={count})")

    # Mild meta-shrinkage
    elif count >= cfg["meta_min_samples"] and win_rate < cfg["meta_threshold"]:
        score_factor *= cfg["meta_score_factor"]
        move_factor *= cfg["meta_move_factor"]
        conf_factor *= cfg["meta_confidence_factor"]
        penalties.append(f"meta_shrink(wr={win_rate:.2f},n={count})")

    # Enforce caps
    score_factor = max(1.0 - MAX_SCORE_REDUCTION, score_factor)
    move_factor = max(1.0 - MAX_MOVE_REDUCTION, move_factor)
    conf_factor = max(1.0 - MAX_CONFIDENCE_REDUCTION, conf_factor)

    return (
        score * score_factor,
        move * move_factor,
        confidence_raw * conf_factor,
        degraded,
        penalties,
    )


# ═══════════════════════════════════════════════════════
# v4.1: Audit Payload Builder
# ═══════════════════════════════════════════════════════

def _build_audit_payload(
    features: dict, regime_data: dict, perf: dict,
    score_raw: float, score_final: float,
    direction_class: str, confidence_raw: float,
    confidence_direction: float, confidence_target: float,
    degraded: bool, penalties: list, baseline_source: str,
    structure_features: dict | None = None,
    structure_influence: dict | None = None,
    structure_multiscale: dict | None = None,
) -> dict:
    payload = {
        "v": "4.1.3-cal",
        "features": {
            "ret_1d": round(features["ret_1d"], 6),
            "ret_7d": round(features["ret_7d"], 6),
            "ret_14d": round(features["ret_14d"], 6),
            "volatility": round(features["volatility"], 6),
            "momentum": round(features["momentum"], 6),
        },
        "regime": regime_data["regime"],
        "regimeConfidence": regime_data["regimeConfidence"],
        "regimeShrinkage": REGIME_SHRINKAGE.get(regime_data["regime"], 0.82),
        "baselineSource": baseline_source,
        "recentSamples": regime_data.get("recentSamples", 0),
        "rollingWinRate": perf.get("rollingWinRate"),
        "scoreRaw": round(score_raw, 6),
        "scoreFinal": round(score_final, 6),
        "directionClass": direction_class,
        "confidenceRaw": round(confidence_raw, 6),
        "confidenceDirection": round(confidence_direction, 4),
        "confidenceTarget": round(confidence_target, 4),
        "degraded": degraded,
        "penalties": penalties,
    }
    if structure_features:
        # Strip internal metadata keys from fused features
        clean = {k: v for k, v in structure_features.items() if not k.startswith("_")}
        payload["structureFeatures"] = clean
    if structure_influence:
        payload["structureInfluence"] = structure_influence
    if structure_multiscale:
        payload["structureMultiscale"] = structure_multiscale
    return payload


def _fetch_exchange_context(db, asset: str) -> dict:
    """Fetch latest exchange observation + funding context for adapter."""
    symbol = f"{asset}USDT"
    obs = db["exchange_observations"].find_one(
        {"symbol": symbol}, {"_id": 0},
        sort=[("timestamp", DESCENDING)],
    )
    funding = db["exchange_funding_context"].find_one(
        {"symbol": symbol}, {"_id": 0},
        sort=[("ts", DESCENDING)],
    )
    whale = db["exchange_whale_events"].find_one(
        {"symbol": symbol}, {"_id": 0},
        sort=[("timestamp", DESCENDING)],
    )
    context = {}
    if obs:
        indicators = obs.get("indicators", {})
        liq = obs.get("liquidations", {})
        oi = obs.get("openInterest", {})
        flow = obs.get("orderFlow", {})
        context["funding_rate"] = indicators.get("funding_pressure", {}).get("value", 0.0) if isinstance(indicators.get("funding_pressure"), dict) else 0.0
        context["open_interest_change"] = oi.get("delta", 0.0)
        context["bullish_patterns"] = obs.get("bullishPatterns", 0)
        context["bearish_patterns"] = obs.get("bearishPatterns", 0)
        context["volume_change"] = obs.get("volume", {}).get("delta", 0.0) if isinstance(obs.get("volume"), dict) else 0.0
        context["liq_long"] = liq.get("longVolume", 0.0)
        context["liq_short"] = liq.get("shortVolume", 0.0)
        context["orderflow_imbalance"] = flow.get("imbalance", 0.0)
    if funding:
        context["funding_score"] = funding.get("fundingScore", 0.0)
    if whale:
        context["whale_volume"] = whale.get("totalSizeUsd", 0.0)
    return context


# ═══════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════

def generate_forecast(asset: str, horizon: Horizon, model_version: str = "v4.1.3", run_id: str = "") -> ForecastRecord | None:
    """
    v4.1 Forecast Generator — Emergency Recovery + Structure Intelligence V2.

    PIPELINE ORDER:
      1. Features
      2. Regime + blended baseline
      2b. Structure feature extraction (from price data)
      3. Directional score (continuous)
      3b. Structure delta applied to score
      4. Direction class (5-state, from score ONLY)
      5. Expected move (regime-anchored)
      6. Raw confidence
      7. Calibrated confidence (direction + target)
      8. Soft degradation (never forces NEUTRAL)
      9. Final payload + audit (incl. structure)
    """
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    horizon_days = HORIZON_DAYS[horizon]
    horizon_key = horizon.value

    # Block 11: Sub-daily bucket + slot
    from forecast.acceleration import (
        get_current_bucket, get_current_slot, get_overlap_group,
        compute_feature_delta, compute_quality_score, MIN_FEATURE_DELTA,
    )
    bucket = get_current_bucket()
    slot = get_current_slot()

    print(f"[PIPELINE] asset={asset}, horizon={horizon_key}, bucket={bucket}")

    start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    prices = get_price_series(asset, start, end)

    features = _compute_features(prices, bucket)
    if not features:
        print(f"[PIPELINE] asset={asset}, horizon={horizon_key} — no features (insufficient price data)")
        return None

    price = features["price"]

    # Block 11: Information Delta Guard — skip if no new information
    db = _get_db()
    last_forecast = db["exchange_forecasts"].find_one(
        {"asset": asset, "horizon": horizon_key, "source": {"$ne": "backfill"}},
        {"_id": 0, "audit": 1},
        sort=[("createdAt", DESCENDING)],
    )
    last_features = (last_forecast.get("audit", {}) or {}).get("features") if last_forecast else None
    feature_delta = compute_feature_delta(features, last_features)

    if feature_delta < MIN_FEATURE_DELTA and slot != "00h":
        print(f"[PIPELINE] asset={asset}, horizon={horizon_key} — SKIP (delta={feature_delta:.4f} < {MIN_FEATURE_DELTA}, insufficient new information)")
        return None

    # Deterministic seed (slot-aware)
    seed_str = f"{bucket}:{horizon.value}:{asset}:{model_version}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    perturbation = ((seed % 1000) / 1000 - 0.5) * 0.02

    # ── Step 2: Regime + blended baseline ──
    regime_data = _get_regime_data(asset, horizon_key, prices)
    regime = regime_data["regime"]
    mean_return = regime_data["meanReturn"]
    std_return = regime_data["stdReturn"]
    mae_mean = regime_data["maeMean"]
    median_return = regime_data["medianReturn"]
    p25_return = regime_data["p25Return"]
    p75_return = regime_data["p75Return"]
    baseline_source = regime_data.get("baselineSource", "unknown")

    regime_shrinkage = REGIME_SHRINKAGE.get(regime, 0.82)

    print(f"[PIPELINE] asset={asset}, horizon={horizon_key}, regime={regime}, price={price:.2f}, baseline={baseline_source}")

    # ── Step 2b: Multi-scale structure feature extraction (v4.1.3: adaptive major) ──
    try:
        multiscale = extract_multiscale(prices)
        mode_info = detect_mode(multiscale["major"], multiscale["minor"])
        structure_features = fuse_major_minor(
            multiscale["major"], multiscale["minor"], mode_info, 0.0,
        )
        structure_multiscale = {
            "major": multiscale["major"],
            "minor": multiscale["minor"],
            "mode": mode_info["mode"],
            "pullback_confidence": mode_info["pullback_confidence"],
            "major_dominant": mode_info["major_dominant"],
            "minor_counter_trend": mode_info["minor_counter_trend"],
            "reversal_candidate": mode_info.get("reversal_candidate", False),
            "major_profile_used": multiscale.get("major_profile_used", "strict"),
            "major_fallback_used": multiscale.get("major_fallback_used", False),
        }
    except Exception:
        structure_features = None
        structure_multiscale = None

    # ── Step: Recent performance (for soft degradation) ──
    perf = _get_recent_performance(asset, horizon_key)

    # Common
    evaluate_after = now_ms + horizon_days * 86_400_000
    forecast_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed_str))

    if horizon_key == "30D":
        record = _generate_30d(
            asset, horizon, horizon_key, horizon_days, model_version, run_id,
            now_ms, bucket, evaluate_after, forecast_id,
            price, features, perturbation,
            regime_data, regime, regime_shrinkage,
            mean_return, std_return, mae_mean, median_return, p25_return, p75_return,
            perf, baseline_source, structure_features, structure_multiscale,
            db=db,
        )
    else:
        record = _generate_7d_24h(
            asset, horizon, horizon_key, horizon_days, model_version, run_id,
            now_ms, bucket, evaluate_after, forecast_id,
            price, features, perturbation,
            regime_data, regime, regime_shrinkage,
            mean_return, std_return, mae_mean, p25_return, p75_return,
            perf, baseline_source, structure_features, structure_multiscale,
            db=db,
        )

    # Block 11: Inject acceleration metadata into audit (post-generation)
    if record and record.audit:
        last_regime = (last_forecast.get("audit", {}) or {}).get("regime") if last_forecast else None
        regime_changed = last_regime is not None and last_regime != regime
        vol_shift = abs(features["volatility"] - (last_features or {}).get("volatility", features["volatility"]))
        quality_score = compute_quality_score(feature_delta, regime_changed, vol_shift)
        record.audit["acceleration"] = {
            "slot": slot,
            "featureDelta": round(feature_delta, 4),
            "regimeChanged": regime_changed,
            "qualityScore": quality_score,
            "overlapGroup": get_overlap_group(asset, horizon_key, bucket),
        }

    return record


# ═══════════════════════════════════════════════════════
# 7D / 24H ENGINE (v4.1)
# ═══════════════════════════════════════════════════════

def _generate_7d_24h(
    asset, horizon, horizon_key, horizon_days, model_version, run_id,
    now_ms, bucket, evaluate_after, forecast_id,
    price, features, perturbation,
    regime_data, regime, regime_shrinkage,
    mean_return, std_return, mae_mean, p25_return, p75_return,
    perf, baseline_source, structure_features=None, structure_multiscale=None,
    db=None,
):
    momentum = features["momentum"]

    # ── Step 3: Directional score (continuous, [-1, 1]) ──
    # bull_score in [0, 1], center 0.5 → remap to [-1, 1]
    bull_score = 0.5 + momentum * 8 + perturbation
    bull_score = max(0.05, min(0.95, bull_score))

    # Remap to centered score: 0→-1, 0.5→0, 1→+1
    directional_score = (bull_score - 0.5) * 2.0

    # Apply regime shrinkage to score (but not to zero)
    score_after_regime = directional_score * regime_shrinkage
    score_raw = score_after_regime

    # ── Step 3b: Structure Intelligence delta ──
    structure_influence = None
    if structure_features:
        struct_result = _structure_optimizer.compute_delta(
            horizon_key, structure_features, score_after_regime,
        )
        # Record A/B shadow comparison (pre-guard values)
        try:
            record_shadow(
                forecast_id=forecast_id,
                asset=asset,
                horizon=horizon_key,
                entry_price=price,
                base_score=score_after_regime,
                structure_score=struct_result["score_after_structure"],
                structure_features=structure_features,
                structure_delta=struct_result["capped_delta"],
                sign_flip=struct_result["sign_flip_allowed"],
                evaluate_after=evaluate_after,
                bucket=bucket,
            )
        except Exception:
            pass  # Shadow recording is non-critical
        # v4.1.2: Apply multiscale guards
        if structure_multiscale:
            struct_result = apply_multiscale_guards(
                struct_result, structure_multiscale, score_after_regime,
            )

        # v4.2.0/v4.2.1: Compute context phase BEFORE override (for phase-aware modulation)
        ctx_features = None
        ctx_phase = None
        if structure_features and structure_multiscale:
            try:
                ctx_features = build_context_features(features, structure_features, structure_multiscale)
                ctx_phase = classify_phase(ctx_features)
            except Exception:
                pass

        # v4.1.3 + v4.2.1: Direction Override Gate (7D/24H only — phase-aware)
        override_result = None
        if structure_multiscale and structure_features and horizon_key != "30D":
            override_result = _override_gate.maybe_override(
                base_score=struct_result["score_after_structure"],
                fused_structure=structure_features,
                mode=structure_multiscale.get("mode", "mixed_range"),
                major_fallback_used=structure_multiscale.get("major_fallback_used", False),
            )
            # v4.2.1: Phase-aware modulation
            if override_result["override_allowed"] and ctx_phase:
                override_result = _override_gate.modulate_override(
                    override_result, ctx_phase["market_phase"],
                )
            if override_result["override_allowed"]:
                struct_result["score_after_structure"] = override_result["override_score"]
        structure_influence = {
            "base_score_before_structure": round(score_after_regime, 6),
            **struct_result,
        }
        if override_result:
            structure_influence["override_gate"] = override_result
        score_after_regime = struct_result["score_after_structure"]

    # ── Step 3c: Market Context Layer (v4.2.0) — confidence/band adjustments ──
    ctx_data = None
    if ctx_features and ctx_phase:
        try:
            ctx_adj = apply_context(
                score=score_after_regime, conf_dir=0.5, conf_tgt=0.5, band_width=1.0,
                ctx=ctx_features, phase=ctx_phase,
            )
            score_after_regime = ctx_adj["score"]
            ctx_data = {
                "features": ctx_features,
                "phase": ctx_phase,
                "adjustments": ctx_adj["adjustments"],
            }
        except Exception:
            pass

    # ── Step 4: Direction class (from score ONLY, before confidence) ──
    active_threshold = get_active_mild_threshold(asset, horizon_key)
    direction = classify_direction(score_after_regime, active_threshold)

    # ── Step 5: Expected move (regime-anchored) ──
    base_shrinkage = 0.75
    total_shrinkage = base_shrinkage * regime_shrinkage

    if direction in ("STRONG_BULL", "MILD_BULL"):
        move_raw = abs(mean_return) * total_shrinkage
    elif direction in ("STRONG_BEAR", "MILD_BEAR"):
        move_raw = -abs(mean_return) * total_shrinkage
    else:
        move_raw = mean_return * total_shrinkage * 0.3

    # Mild directions get smaller move than strong
    if direction.startswith("MILD"):
        move_raw *= 0.7

    # Volatility adjustment
    vol_ratio = min(2.0, max(0.5, features["volatility"] / max(0.005, std_return * 0.15)))
    move_adjusted = move_raw * vol_ratio

    # CAP at 1.5 * MAE
    move_cap = 1.5 * mae_mean
    move_adjusted = max(-move_cap, min(move_cap, move_adjusted))

    # Optimism guard: cap at p90
    p90_guard = p75_return + 0.75 * (p75_return - p25_return)
    if move_adjusted > 0 and move_adjusted > p90_guard:
        move_adjusted = p90_guard
    elif move_adjusted < 0 and abs(move_adjusted) > abs(p90_guard):
        move_adjusted = -abs(p90_guard)

    # ── Step 6: Raw confidence (computed independently from direction) ──
    dir_hit_rate = regime_data["dirHitMean"]
    regime_confidence = regime_data["regimeConfidence"]
    vol_percentile = min(1.0, features["volatility"] / 0.04)
    vol_penalty = 1.0 - vol_percentile * 0.2  # Softened from 0.3

    confidence_raw = dir_hit_rate * regime_confidence * vol_penalty
    confidence_raw = max(0.05, min(0.95, confidence_raw))

    # ── Step 7: Calibrated confidence (Block 8.1 — data-driven per-horizon) ──
    confidence_direction = _calibrate_direction(confidence_raw, horizon_key)
    confidence_target = _calibrate_target(confidence_raw, horizon_key)

    # v4.2.0: Apply context confidence adjustments
    if ctx_data:
        confidence_direction *= ctx_data["adjustments"]["conf_dir_mult"]
        confidence_target *= ctx_data["adjustments"]["conf_tgt_mult"]
        confidence_direction = max(0.05, min(0.95, confidence_direction))
        confidence_target = max(0.05, min(0.95, confidence_target))

    # ── Step 7b: Regime Engine V2 (v4.3.0) — probability-based adjustments ──
    regime_v2_data = None
    if ctx_features and ctx_phase:
        try:
            regime_feats = build_regime_features(
                features, structure_features or {}, ctx_features,
                structure_multiscale or {"major": {}, "minor": {}, "mode": "mixed_range"},
            )
            regime_probs = compute_regime_probabilities(regime_feats,
                context_phase=ctx_phase.get("market_phase", "mixed_range") if ctx_phase else "mixed_range")
            regime_post = postprocess_regime(regime_probs)
            regime_adj = apply_regime_adjustments(
                score=score_after_regime,
                conf_dir=confidence_direction,
                conf_tgt=confidence_target,
                band_mult=1.0,
                regime=regime_post,
                regime_features=regime_feats,
                context_phase=ctx_phase.get("market_phase", "mixed_range") if ctx_phase else None,
            )
            confidence_direction = max(0.05, min(0.95, regime_adj["conf_dir"]))
            confidence_target = max(0.05, min(0.95, regime_adj["conf_tgt"]))
            regime_v2_data = {
                "features": regime_feats,
                "regime": regime_post,
                "adjustments": regime_adj["adjustments"],
            }
        except Exception:
            pass

    # ── Step 8: Soft degradation (NEVER forces NEUTRAL) ──
    score_final, move_final, conf_final, degraded, penalties = _apply_soft_degradation(
        score_after_regime, move_adjusted, confidence_raw, perf,
    )

    # Re-classify direction after soft degradation
    # (direction MAY shift from strong→mild, but NEVER into forced NEUTRAL)
    direction_after = classify_direction(score_final, active_threshold)
    # Guard: if raw score was directional, final can't be NEUTRAL
    if direction != "NEUTRAL" and direction_after == "NEUTRAL":
        direction_after = direction.replace("STRONG_", "MILD_")
        if not direction_after.startswith("MILD"):
            direction_after = direction

    direction = direction_after

    # Recalibrate confidence after degradation
    if degraded:
        confidence_direction = _calibrate_direction(conf_final, horizon_key)
        confidence_target = _calibrate_target(conf_final, horizon_key)

    # Use direction confidence as main confidence for backward compat
    confidence = round(max(0.10, min(0.85, confidence_direction)), 4)

    move_pct = round(move_final * 100, 2)
    target_price = round(price * (1 + move_pct / 100), 2)

    # Map 5-state to legacy direction for backward compat in evaluator
    legacy_direction = _to_legacy_direction(direction)

    # ── Step D1: Decision Layer V1 — override legacy direction ──
    decision_output = None
    _interaction_output = None
    try:
        # Derive scenario probabilities for 7D/24H (no ScenarioEngine here)
        _forecast_dir = direction.lower().replace("strong_", "").replace("mild_", "")
        if _forecast_dir in ("bull", "bear"):
            _forecast_dir = _forecast_dir + "ish"
        elif _forecast_dir not in ("bullish", "bearish", "neutral"):
            _forecast_dir = "neutral"

        _regime_entropy = 1.0 - min(1.0, regime_data.get("regimeConfidence", 0.5))
        _bull_struct_legacy = _compute_bullish_structure(structure_features)
        _bear_struct_legacy = _compute_bearish_structure(structure_features, ctx_data.get("features") if ctx_data else None)

        # DRR-powered bearish_structure when regime_v2 data is available
        if regime_v2_data and regime_v2_data.get("features"):
            _rv2_feats = regime_v2_data["features"]
            _rv2_regime = regime_v2_data["regime"]
            _bear_struct_drr = _compute_bearish_structure_drr(
                _rv2_feats, _rv2_regime, base_bearish=_bear_struct_legacy,
            )
            # Unified Structure Engine V2 (blending)
            _drr_out = _drr_engine.compute(DRRInputs(
                trend_strength=_rv2_feats.get("trend_strength", 0.5),
                trend_persistence=_rv2_feats.get("trend_persistence", 0.5),
                exhaustion=_rv2_feats.get("exhaustion", 0.0),
                reversal_risk=_rv2_feats.get("reversal_risk", 0.0),
                drawdown_pressure=_rv2_feats.get("drawdown_pressure", 0.0),
                structure_alignment=_rv2_feats.get("structure_alignment", 0.5),
                volatility_expansion=_rv2_feats.get("volatility_expansion", 0.0),
                dominant_regime=_rv2_regime.get("dominant_regime", "range"),
                breakdown_prob=_rv2_regime.get("probabilities", {}).get("breakdown", 0.05),
            ))
            _struct_v2 = _structure_engine.evaluate(StructureInputs(
                trend_strength=_rv2_feats.get("trend_strength", 0.5),
                trend_persistence=_rv2_feats.get("trend_persistence", 0.5),
                momentum=_rv2_feats.get("exhaustion", 0.5),
                structure_alignment=_rv2_feats.get("structure_alignment", 0.5),
                volatility_expansion=_rv2_feats.get("volatility_expansion", 0.0),
                drawdown_pressure=_drr_out.drawdown_pressure,
                reversal_risk=_drr_out.reversal_risk,
                breakdown_risk=_drr_out.breakdown_risk,
                regime=_rv2_regime.get("dominant_regime", "range"),
            ))
            # Blend legacy with V2
            _w = STRUCTURE_V2_BLEND
            _bull_struct = (1 - _w) * _bull_struct_legacy + _w * _struct_v2.bullish_structure
            _bear_struct = (1 - _w) * _bear_struct_drr + _w * _struct_v2.bearish_structure
        else:
            _bull_struct = _bull_struct_legacy
            _bear_struct = _bear_struct_legacy

        _ctx_align = (ctx_data["features"].get("trend_strength", 0.5) * ctx_data["features"].get("trend_persistence", 0.5)) if ctx_data and ctx_data.get("features") else 0.5
        _neg_ctx = ctx_data["features"].get("drawdown_pressure", 0.0) if ctx_data and ctx_data.get("features") else 0.0

        scenario_probs = derive_scenario_probs(
            forecast_direction=_forecast_dir,
            calibrated_confidence=confidence_direction,
            regime_entropy=_regime_entropy,
            bullish_structure=_bull_struct,
            bearish_structure=_bear_struct,
            context_alignment=_ctx_align,
            negative_context=_neg_ctx,
        )

        # ── Interaction Layer V1 (Shadow Mode) ──
        if INTERACTION_ENABLED:
            try:
                if regime_v2_data and regime_v2_data.get("features"):
                    _il_state = _struct_v2.structure_state
                    _il_clarity = _struct_v2.structure_clarity
                    _il_regime = _rv2_regime.get("dominant_regime", "range")
                else:
                    _il_state = "mixed"
                    _il_clarity = 0.3
                    _il_regime = regime.lower() if regime else "range"

                _il_inp = _InteractionInputs(
                    structure_state=_il_state,
                    structure_clarity=_il_clarity,
                    bullish_structure=_bull_struct,
                    bearish_structure=_bear_struct,
                    dominant_regime=_il_regime,
                    regime_entropy=_regime_entropy,
                    dominant_scenario=scenario_probs["dominant_scenario"],
                    bullish_prob=scenario_probs["bullish_prob"],
                    base_prob=scenario_probs["base_prob"],
                    bearish_prob=scenario_probs["bearish_prob"],
                    calibrated_confidence=confidence_direction,
                    expected_move_pct=abs(move_pct),
                )
                _interaction_output = _interaction_layer.evaluate(_il_inp)
                print(f"[INTERACTION_V1] {asset}/{horizon_key}: state={_interaction_output.interaction_state} align={_interaction_output.alignment_score:.3f} conflict={_interaction_output.conflict_score:.3f} conf_mod={_interaction_output.confidence_modifier:.3f} bias_mod={_interaction_output.decision_bias_modifier:.3f}")

                # Stage 2: Apply confidence modifier (when enabled)
                if INTERACTION_USE_CONFIDENCE and not INTERACTION_KILL_SWITCH:
                    _conf_before = confidence_direction
                    _conf_scale = INTERACTION_CONF_SCALE.get(horizon_key, 0.60)
                    # V2 state-aware blending (when enabled)
                    if META_V2_ENABLED and META_V2_USE_CONFIDENCE:
                        _state_group = resolve_state_group(_interaction_output.interaction_state)
                        _v2_snap = getattr(_interaction_layer, '_meta_v2_snap', {}).get(horizon_key)
                        if _v2_snap and _state_group in _v2_snap.conf_scales:
                            _v2_scale = _v2_snap.conf_scales[_state_group]
                            _conf_scale = MetaCalibrationLayerV2.compute_blend(
                                _conf_scale, _v2_scale, META_V2_BLEND_WITH_V1,
                            )
                    _raw_delta = _conf_scale * _interaction_output.confidence_modifier
                    _raw_delta = max(INTERACTION_CONF_PRECLIP[0], min(INTERACTION_CONF_PRECLIP[1], _raw_delta))
                    confidence_direction = max(0.05, min(0.95, confidence_direction + _raw_delta))
                    _conf_after = confidence_direction
                    print(f"[STAGE2] {asset}/{horizon_key}: conf {_conf_before:.4f} → {_conf_after:.4f} (Δ={_conf_after - _conf_before:+.4f}, scale={_conf_scale:.3f})")

            except Exception as e:
                print(f"[INTERACTION_V1] {asset}/{horizon_key}: shadow error ({e})")

        d_inputs = DecisionInputs(
            asset=asset,
            horizon=horizon_key,
            calibrated_confidence=confidence_direction,
            forecast_direction=_forecast_dir,
            regime_entropy=_regime_entropy,
            regime_gap=_compute_regime_gap(regime_v2_data["regime"].get("probabilities") if regime_v2_data and regime_v2_data.get("regime") else None),
            dominant_regime=regime.lower() if regime else "range",
            structure_strength=structure_features.get("structure_stability_score", 0.5) if structure_features else 0.5,
            bullish_structure=_bull_struct,
            bearish_structure=_bear_struct,
            context_alignment=_ctx_align,
            negative_context=_neg_ctx,
            expected_move_pct=abs(move_pct),
            dominant_scenario=scenario_probs["dominant_scenario"],
            dominant_scenario_prob=scenario_probs["dominant_scenario_prob"],
            bullish_prob=scenario_probs["bullish_prob"],
            base_prob=scenario_probs["base_prob"],
            bearish_prob=scenario_probs["bearish_prob"],
        )
        decision_output = _decision_layer.decide(d_inputs)
        legacy_direction = decision_output.direction
        _neutral_reason = ""
        if decision_output.direction == "NEUTRAL" and decision_output.rationale:
            _neutral_reason = f" reason=[{', '.join(decision_output.rationale)}]"
        print(f"[DECISION_V1] {asset}/{horizon_key}: {decision_output.direction} mode={decision_output.decision_mode} str={decision_output.decision_strength:.3f} bull_s={d_inputs.bullish_structure:.3f} bear_s={d_inputs.bearish_structure:.3f} bull_p={d_inputs.bullish_prob:.3f} bear_p={d_inputs.bearish_prob:.3f} entropy={d_inputs.regime_entropy:.3f}{_neutral_reason}")
    except Exception as e:
        print(f"[DECISION_V1] {asset}/{horizon_key}: fallback to legacy ({e})")

    immutable_hash = hashlib.sha256(
        f"{forecast_id}:{target_price}:{direction}:{confidence}".encode()
    ).hexdigest()[:16]

    # ── Step 9: Audit payload ──
    audit = _build_audit_payload(
        features, regime_data, perf,
        score_raw, score_final,
        direction, confidence_raw,
        confidence_direction, confidence_target,
        degraded, penalties, baseline_source,
        structure_features=structure_features,
        structure_influence=structure_influence,
        structure_multiscale=structure_multiscale,
    )
    # Block 8.1: Calibration metadata
    audit["calibration"] = get_calibration_info(horizon_key)
    audit["threshold_config"] = {
        "active_threshold": active_threshold,
        "default_threshold": 0.20,
        "in_rollout": active_threshold != 0.20,
    }

    # v4.2.0: Add context audit
    if ctx_data:
        audit["marketContext"] = ctx_data["features"]
        audit["contextPhase"] = ctx_data["phase"]
        audit["contextAdjustments"] = ctx_data["adjustments"]

    # v4.3.0: Add regime audit
    if regime_v2_data:
        regime_audit = build_regime_audit(
            regime_v2_data["features"], regime_v2_data["regime"], regime_v2_data,
        )
        audit["regimeV2"] = regime_audit["regime_v2"]
        audit["regimeAdjustments"] = regime_audit["regime_adjustments"]

    # D1: Decision Layer audit
    if decision_output:
        audit["decisionLayer"] = {
            "direction": decision_output.direction,
            "mode": decision_output.decision_mode,
            "strength": decision_output.decision_strength,
            "confidence": decision_output.decision_confidence,
            "rationale": decision_output.rationale,
            "scores": decision_output.audit,
        }
        # Structure V2 audit (shadow/blended)
        if regime_v2_data and regime_v2_data.get("features"):
            try:
                audit["structure_v2"] = {
                    "bullish": round(_struct_v2.bullish_structure, 4),
                    "bearish": round(_struct_v2.bearish_structure, 4),
                    "clarity": round(_struct_v2.structure_clarity, 4),
                    "state": _struct_v2.structure_state,
                    "components": _struct_v2.audit,
                    "blend_weight": STRUCTURE_V2_BLEND,
                }
            except Exception:
                pass

    # Interaction Layer V1 audit (shadow)
    if _interaction_output:
        _state_grp = resolve_state_group(_interaction_output.interaction_state)
        _i_audit = {
            "state": _interaction_output.interaction_state,
            "state_group": _state_grp,
            "alignment_score": _interaction_output.alignment_score,
            "conflict_score": _interaction_output.conflict_score,
            "confidence_modifier": _interaction_output.confidence_modifier,
            "decision_bias_modifier": _interaction_output.decision_bias_modifier,
            "scenario_mods": {
                "bullish": _interaction_output.bullish_scenario_modifier,
                "base": _interaction_output.base_scenario_modifier,
                "bearish": _interaction_output.bearish_scenario_modifier,
            },
            "rationale": _interaction_output.rationale,
            "polarity": _interaction_output.audit,
        }
        # Shadow baseline: before/after/delta for Stage 2 analysis
        try:
            _i_audit["confidence_before_interaction"] = round(_conf_before, 4)
            _i_audit["confidence_after_interaction"] = round(_conf_after, 4)
            _i_audit["confidence_delta"] = round(_conf_after - _conf_before, 4)
        except NameError:
            pass
        audit["interaction"] = _i_audit

    # ── Exchange Signal Adapter ──
    _exchange_db = db if db is not None else _get_db()
    _exchange_signal_data = None
    try:
        exchange_ctx = _fetch_exchange_context(_exchange_db, asset)
        _exchange_signal_data = build_exchange_signal(exchange_ctx)
        _decision_for_bias = {"direction": direction, "confidence": confidence}
        _decision_for_bias = apply_exchange_bias(_decision_for_bias, _exchange_signal_data)
        audit["exchange_signal"] = _exchange_signal_data
        audit["exchange_bias"] = _decision_for_bias.get("exchange_bias_audit", {})
        audit["exchange_context"] = exchange_ctx
    except Exception as exc:
        audit["exchange_signal_error"] = str(exc)

    # ── Forecast V2 (shadow mode — C3) ──
    try:
        from forecast.forecast_v2 import compute_forecast_v2
        _fv2_result = compute_forecast_v2(
            base_score=score_final,
            exchange_signal=_exchange_signal_data or {},
            audit=audit,
            features=features,
            price=price,
            db=_exchange_db,
            asset=asset,
            horizon=horizon,
        )
        audit["forecast_v2"] = _fv2_result
        audit["forecast_v1_score"] = round(score_final, 6)
        audit["forecast_v2_score"] = _fv2_result.get("final_score", score_final)
    except Exception as exc:
        audit["forecast_v2_error"] = str(exc)

    # ── Decision V2 (shadow mode — C2) ──
    # Use V2 score if available for Decision V2
    _decision_base_score = audit.get("forecast_v2_score", score_final) if audit.get("forecast_v2") else score_final
    try:
        from forecast.decision_v2 import compute_decision_v2
        _v2_result = compute_decision_v2(
            base_score=_decision_base_score,
            exchange_signal=_exchange_signal_data or {},
            audit=audit,
            v1_direction=legacy_direction,
            v1_confidence=confidence,
        )
        audit["decision_v2"] = _v2_result
    except Exception as exc:
        audit["decision_v2_error"] = str(exc)

    # ── System Convergence: V2 Live Routing ──
    _final_direction = legacy_direction
    _final_confidence = confidence
    try:
        from forecast.convergence import apply_v2_to_forecast
        _fv2 = audit.get("forecast_v2", {})
        _dv2 = audit.get("decision_v2", {})
        _final_direction, _final_confidence, _, _conv_audit = apply_v2_to_forecast(
            forecast_id=forecast_id,
            v1_direction=legacy_direction,
            v1_confidence=confidence,
            v1_score=score_final,
            forecast_v2_result=_fv2,
            decision_v2_result=_dv2,
        )
        audit["convergence"] = _conv_audit
    except Exception as exc:
        audit["convergence_error"] = str(exc)

    # ── System Aggregator (shadow mode — BLOCK 3) ──
    try:
        from forecast.system.aggregator import (
            AggregatorInputs, compute_aggregated_signal, aggregator_to_audit,
        )
        from forecast.system.sentiment_adapter import fetch_sentiment_for_asset
        from forecast.system.fractal_adapter import fetch_fractal_signal

        _agg_db = db if db is not None else _get_db()
        _sentiment = fetch_sentiment_for_asset(_agg_db, asset)
        _fractal = fetch_fractal_signal(_agg_db, asset)

        _dv2 = audit.get("decision_v2", {}) or {}
        _fv2_score = audit.get("forecast_v2_score", score_final)
        _micro_bias = (_exchange_signal_data or {}).get("micro_bias", 0)
        _regime_dir = _dv2.get("regime_direction", "RANGE")
        _conflict = (audit.get("interaction", {}) or {}).get("conflict_score", 0) or 0

        _agg_input = AggregatorInputs(
            forecast_score=_fv2_score,
            exchange_bias=_micro_bias,
            sentiment_score=_sentiment["score"],
            sentiment_confidence=_sentiment["confidence"],
            fractal_signal=_fractal["signal"],
            fractal_confidence=_fractal["confidence"],
            regime=_regime_dir,
            conflict_score=_conflict,
            horizon=horizon,
        )
        _agg_output = compute_aggregated_signal(_agg_input)
        audit["aggregator_v1"] = aggregator_to_audit(_agg_output)
        audit["aggregator_v1"]["sentiment_input"] = _sentiment
        audit["aggregator_v1"]["fractal_input"] = _fractal

        # ── Controlled Live Routing ──
        from forecast.system.aggregator import apply_aggregator_to_forecast
        _agg_live = apply_aggregator_to_forecast(
            forecast_id=str(audit.get("signalId", "")),
            current_direction=_final_direction,
            current_confidence=_final_confidence,
            current_score=score_final,
            agg_output=_agg_output,
            exchange_bias=_micro_bias,
            horizon=horizon,
        )
        audit["aggregator_live"] = _agg_live["telemetry"]
        if _agg_live["telemetry"]["used"]:
            _final_direction = _agg_live["direction"]
            _final_confidence = _agg_live["confidence"]
            score_final = _agg_live["score"]
            # Emit aggregator signal for high-confidence live decisions
            if _final_confidence >= 0.7 and _final_direction != "NEUTRAL":
                try:
                    from notifications.emit import emit_aggregator_signal
                    import asyncio
                    asyncio.get_event_loop().create_task(
                        emit_aggregator_signal(
                            asset=asset,
                            direction=_final_direction,
                            confidence=_final_confidence,
                            details={"components": _agg_output.components, "horizon": horizon},
                        )
                    )
                except Exception:
                    pass
    except Exception as exc:
        audit["aggregator_error"] = str(exc)

    # ── Decision Trace (PLO enrichment — read-only logging) ──
    audit["decision_trace"] = {
        "base_score": round(score_final, 6),
        "exchange_bias": round((_exchange_signal_data or {}).get("micro_bias", 0), 4),
        "forecast_v2_score": round(audit.get("forecast_v2_score", score_final), 6),
        "decision_v2_direction": (audit.get("decision_v2") or {}).get("direction", "N/A"),
        "decision_v2_confidence": (audit.get("decision_v2") or {}).get("confidence", 0),
        "thresholds": {
            "long": (audit.get("decision_v2") or {}).get("thresholds", {}).get("long", 0.10),
            "short": (audit.get("decision_v2") or {}).get("thresholds", {}).get("short", -0.10),
            "dynamic": (audit.get("decision_v2") or {}).get("thresholds", {}).get("dynamic", False),
        },
        "regime_direction": (audit.get("decision_v2") or {}).get("regime_direction", "UNKNOWN"),
        "reversal_signal": (audit.get("decision_v2") or {}).get("reversal_signal", False),
        "anti_trap": (audit.get("decision_v2") or {}).get("anti_trap_applied", False),
        "final_direction": _final_direction,
        "final_confidence": round(_final_confidence, 4),
        "system_version": (audit.get("convergence") or {}).get("system_version", "V1"),
        "aggregator_direction": (audit.get("aggregator_v1") or {}).get("direction", "N/A"),
        "aggregator_confidence": (audit.get("aggregator_v1") or {}).get("confidence", 0),
    }

    return ForecastRecord(
        id=forecast_id,
        asset=asset,
        symbol=f"{asset}USDT",
        horizon=horizon,
        horizonDays=horizon_days,
        runId=run_id,
        createdAt=now_ms,
        createdBucket=bucket,
        evaluateAfter=evaluate_after,
        entryPrice=round(price, 2),
        targetPrice=target_price,
        expectedMovePct=move_pct,
        direction=_final_direction,
        confidence=_final_confidence,
        confidenceRaw=round(confidence_raw, 4),
        modelVersion=model_version,
        featuresHash=features["features_hash"],
        immutableHash=immutable_hash,
        dataWindowEnd=now_ms,
        source="scheduler",
        directionClass=direction,
        confidenceDirection=round(confidence_direction, 4),
        confidenceTarget=round(confidence_target, 4),
        degraded=degraded,
        audit=audit,
    )


# ═══════════════════════════════════════════════════════
# 30D ENGINE (v4.1)
# ═══════════════════════════════════════════════════════

def _generate_30d(
    asset, horizon, horizon_key, horizon_days, model_version, run_id,
    now_ms, bucket, evaluate_after, forecast_id,
    price, features, perturbation,
    regime_data, regime, regime_shrinkage,
    mean_return, std_return, mae_mean, median_return, p25_return, p75_return,
    perf, baseline_source, structure_features=None, structure_multiscale=None,
    db=None,
):
    # Bands = raw regime percentiles (honest range)
    band_core_low = round(price * (1 + p25_return), 2)
    band_core_high = round(price * (1 + p75_return), 2)

    iqr = p75_return - p25_return
    p10_est = p25_return - 0.75 * iqr
    p90_est = p75_return + 0.75 * iqr
    band_wide_low = round(price * (1 + p10_est), 2)
    band_wide_high = round(price * (1 + p90_est), 2)

    # ── Step 3: Directional score for 30D ──
    # Use median_return + momentum blend as continuous score
    norm_median = median_return / max(std_return, 0.001)
    momentum_contrib = features["momentum"] * 4
    score_30d = norm_median * 0.6 + momentum_contrib * 0.4 + perturbation
    score_30d = max(-1.0, min(1.0, score_30d))

    score_after_regime = score_30d * regime_shrinkage
    score_raw = score_after_regime

    # ── Step 3b: Structure Intelligence delta ──
    structure_influence = None
    if structure_features:
        struct_result = _structure_optimizer.compute_delta(
            horizon_key, structure_features, score_after_regime,
        )
        # Record A/B shadow comparison (pre-guard values)
        try:
            record_shadow(
                forecast_id=forecast_id,
                asset=asset,
                horizon=horizon_key,
                entry_price=price,
                base_score=score_after_regime,
                structure_score=struct_result["score_after_structure"],
                structure_features=structure_features,
                structure_delta=struct_result["capped_delta"],
                sign_flip=struct_result["sign_flip_allowed"],
                evaluate_after=evaluate_after,
                bucket=bucket,
            )
        except Exception:
            pass  # Shadow recording is non-critical
        # v4.1.2: Apply multiscale guards
        if structure_multiscale:
            struct_result = apply_multiscale_guards(
                struct_result, structure_multiscale, score_after_regime,
            )
        # v4.1.3: Direction Override Gate (disabled for 30D — not validated)
        override_result = None
        structure_influence = {
            "base_score_before_structure": round(score_after_regime, 6),
            **struct_result,
        }
        score_after_regime = struct_result["score_after_structure"]

    # ── Step 4: Direction class (from score ONLY) ──
    active_threshold = get_active_mild_threshold(asset, horizon_key)
    direction = classify_direction(score_after_regime, active_threshold)

    # ── Step 5: Median target with shrinkage ──
    shrinkage = 0.75 * regime_shrinkage
    median_target = round(price * (1 + median_return * shrinkage), 2)

    move_raw = median_return * shrinkage
    if direction.startswith("MILD"):
        move_raw *= 0.8

    # ── Step 6: Raw confidence (Block 8.2.1 — diversified multi-source) ──
    # OLD formula: signal_strength * 0.7 → always 0.10 (information collapse)
    # NEW: base + structure_boost + regime_boost + range_clarity - vol_penalty
    base_conf = 0.35

    # 1. Signal strength contribution (directional clarity)
    signal_strength = abs(score_30d)
    signal_boost = min(0.15, signal_strength * 0.3)

    # 2. Regime clarity (higher regimeConfidence → more trust)
    regime_clarity = min(1.0, regime_data["regimeConfidence"])
    regime_boost = 0.10 * regime_clarity

    # 3. Structure alignment (if available)
    structure_boost = 0.0
    if structure_features:
        # stability + trend clarity = higher confidence
        stability = structure_features.get("structure_stability_score", 0.5)
        trend_clarity = abs(structure_features.get("structure_trend_score", 0.0))
        compression = structure_features.get("structure_compression_score", 0.0)
        structure_boost = 0.08 * stability + 0.07 * trend_clarity
        # Compression (low vol regime) slightly increases confidence for range
        if compression > 0.6:
            structure_boost += 0.03

    # 4. Range narrowness (narrow IQR → more certain)
    range_width = abs(p75_return - p25_return) if p75_return and p25_return else 0.10
    range_norm = max(0.0, 1.0 - range_width / 0.20)  # normalize: 20% width → 0 boost
    range_boost = 0.05 * range_norm

    # 5. Volatility penalty (high vol → less confidence)
    vol_percentile = min(1.0, features["volatility"] / 0.04)
    vol_penalty = vol_percentile * 0.10

    confidence_raw = base_conf + signal_boost + regime_boost + structure_boost + range_boost - vol_penalty
    confidence_raw = max(0.15, min(0.75, confidence_raw))

    # ── Step 7: Calibrated confidence (Block 8.1 — data-driven per-horizon) ──
    confidence_direction = _calibrate_direction(confidence_raw, horizon_key)
    confidence_target = _calibrate_target(confidence_raw, horizon_key)

    # ── Step 8: Soft degradation ──
    score_final, move_final, conf_final, degraded, penalties = _apply_soft_degradation(
        score_after_regime, move_raw, confidence_raw, perf,
    )

    direction_after = classify_direction(score_final, active_threshold)
    if direction != "NEUTRAL" and direction_after == "NEUTRAL":
        direction_after = direction.replace("STRONG_", "MILD_")
        if not direction_after.startswith("MILD"):
            direction_after = direction
    direction = direction_after

    if degraded:
        confidence_direction = _calibrate_direction(conf_final, horizon_key)
        confidence_target = _calibrate_target(conf_final, horizon_key)

    confidence = round(max(0.10, min(0.85, confidence_direction)), 4)

    target_price = round(price * (1 + move_final), 2) if move_final != move_raw else median_target
    move_pct = round(((target_price - price) / price) * 100, 2)

    legacy_direction = _to_legacy_direction(direction)

    immutable_hash = hashlib.sha256(
        f"{forecast_id}:{target_price}:{direction}:{confidence}".encode()
    ).hexdigest()[:16]

    audit = _build_audit_payload(
        features, regime_data, perf,
        score_raw, score_final,
        direction, confidence_raw,
        confidence_direction, confidence_target,
        degraded, penalties, baseline_source,
        structure_features=structure_features,
        structure_influence=structure_influence,
        structure_multiscale=structure_multiscale,
    )
    # Block 8.1: Calibration metadata
    audit["calibration"] = get_calibration_info(horizon_key)
    audit["threshold_config"] = {
        "active_threshold": active_threshold,
        "default_threshold": 0.20,
        "in_rollout": active_threshold != 0.20,
    }

    # ── Step 9b: Scenario Engine V2 (Block 9) ──
    scenario_set = None
    try:
        # Build context and regime probabilities for scenario engine
        ctx_features_30d = None
        ctx_phase_30d = None
        regime_probs_30d = None
        regime_entropy_30d = 1.0 - min(1.0, regime_data.get("regimeConfidence", 0.5))

        try:
            if structure_features:
                ctx_features_30d = build_context_features(features, structure_features, structure_multiscale)
                ctx_phase_30d = classify_phase(ctx_features_30d)
                regime_feats = build_regime_features(
                    features, structure_features or {}, ctx_features_30d,
                    structure_multiscale or {"major": {}, "minor": {}, "mode": "mixed_range"},
                )
                regime_probs_30d = compute_regime_probabilities(regime_feats)
                regime_post_30d = postprocess_regime(regime_probs_30d)
        except Exception:
            regime_feats = None
            regime_post_30d = None

        # Build TruthInputs for V2 engine
        truth = TruthInputs(
            asset=asset,
            horizon=horizon_key,
            spot_price=price,
            direction=direction.lower().replace("strong_", "").replace("mild_", ""),
            calibrated_confidence=confidence_direction,
            regime_probs=regime_probs_30d or {},
            dominant_regime=regime.lower() if regime else "range",
            regime_entropy=regime_entropy_30d,
            regime_gap=_compute_regime_gap(regime_probs_30d),
            structure_strength=structure_features.get("structure_stability_score", 0.5) if structure_features else 0.5,
            bullish_structure=_compute_bullish_structure(structure_features),
            bearish_structure=_compute_bearish_structure_drr(regime_feats, regime_post_30d, _compute_bearish_structure(structure_features, ctx_features_30d)) if regime_feats and regime_post_30d else _compute_bearish_structure(structure_features, ctx_features_30d),
            context_alignment=(
                ctx_features_30d.get("trend_strength", 0.5) * ctx_features_30d.get("trend_persistence", 0.5)
            ) if ctx_features_30d else 0.5,
            negative_context=ctx_features_30d.get("drawdown_pressure", 0.0) if ctx_features_30d else 0.0,
            volatility_norm=min(1.0, features["volatility"] / 0.04),
            expected_move_pct=abs(move_raw) if move_raw else 0.05,
            range_state_score=_compute_range_state(structure_features),
            drawdown_pressure=ctx_features_30d.get("drawdown_pressure", 0.0) if ctx_features_30d else 0.0,
        )

        scenario_set = _scenario_engine_v2.build(truth)

        # Strip audit fields for storage
        if scenario_set and "_audit" in scenario_set:
            audit["scenarioAudit"] = scenario_set.pop("_audit", None)

    except Exception as e:
        # Fallback to V1 assembler if V2 fails
        print(f"[SCENARIO_V2] Fallback to V1: {e}")
        try:
            structure_bias = structure_features.get("structure_bias_score", 0.0) if structure_features else 0.0
            mode = structure_multiscale.get("mode", "mixed_range") if structure_multiscale else "mixed_range"
            scenario_input = {
                "momentum": features["momentum"],
                "volatility": features["volatility"],
                "ret_7d": features["ret_7d"],
                "ret_14d": features["ret_14d"],
                "median_return": median_return,
                "std_return": std_return,
                "p25_return": p25_return,
                "p75_return": p75_return,
                "mean_return": mean_return,
                "structure_bias": structure_bias,
                "mode": mode,
                "regime_probs": regime_probs_30d,
                "dominant_regime": regime.lower() if regime else "range",
                "regime_entropy": regime_entropy_30d,
                "decision_uncertainty": 0.5,
                "context_phase": ctx_phase_30d.get("market_phase") if ctx_phase_30d else None,
            }
            scenario_set = build_scenarios(scenario_input)
            if scenario_set and "_audit" in scenario_set:
                audit["scenarioAudit"] = scenario_set.pop("_audit", None)
        except Exception:
            pass

    # ── Step D1: Decision Layer V1 (30D) — use real scenario probs ──
    decision_output_30d = None
    _interaction_output_30d = None
    try:
        _forecast_dir_30d = direction.lower().replace("strong_", "").replace("mild_", "")
        if _forecast_dir_30d in ("bull", "bear"):
            _forecast_dir_30d = _forecast_dir_30d + "ish"
        elif _forecast_dir_30d not in ("bullish", "bearish", "neutral"):
            _forecast_dir_30d = "neutral"

        # Extract scenario probabilities from scenario_set (if available)
        _bull_prob_30d, _base_prob_30d, _bear_prob_30d = 0.33, 0.34, 0.33
        _dom_scenario_30d, _dom_prob_30d = "base", 0.34
        if scenario_set and "scenarios" in scenario_set:
            for sc in scenario_set["scenarios"]:
                if sc.get("name") == "bullish":
                    _bull_prob_30d = sc.get("probability", 0.33)
                elif sc.get("name") == "base":
                    _base_prob_30d = sc.get("probability", 0.34)
                elif sc.get("name") == "bearish":
                    _bear_prob_30d = sc.get("probability", 0.33)
            _probs_map = {"bullish": _bull_prob_30d, "base": _base_prob_30d, "bearish": _bear_prob_30d}
            _dom_scenario_30d = max(_probs_map, key=_probs_map.get)
            _dom_prob_30d = _probs_map[_dom_scenario_30d]
        elif scenario_set:
            # Try flat keys
            _bull_prob_30d = scenario_set.get("bullish_prob", scenario_set.get("bullish", {}).get("probability", 0.33))
            _base_prob_30d = scenario_set.get("base_prob", scenario_set.get("base", {}).get("probability", 0.34))
            _bear_prob_30d = scenario_set.get("bearish_prob", scenario_set.get("bearish", {}).get("probability", 0.33))
            _probs_map = {"bullish": _bull_prob_30d, "base": _base_prob_30d, "bearish": _bear_prob_30d}
            _dom_scenario_30d = max(_probs_map, key=_probs_map.get)
            _dom_prob_30d = _probs_map[_dom_scenario_30d]

        _bull_struct_30d_legacy = _compute_bullish_structure(structure_features)
        _bear_struct_30d_legacy = _compute_bearish_structure(structure_features, ctx_features_30d)
        _bear_struct_30d_drr = _compute_bearish_structure_drr(regime_feats, regime_post_30d, _bear_struct_30d_legacy) if regime_feats and regime_post_30d else _bear_struct_30d_legacy

        # Unified Structure Engine V2 for 30D
        _struct_v2_30d = None
        if regime_feats:
            _drr_out_30d = _drr_engine.compute(DRRInputs(
                trend_strength=regime_feats.get("trend_strength", 0.5),
                trend_persistence=regime_feats.get("trend_persistence", 0.5),
                exhaustion=regime_feats.get("exhaustion", 0.0),
                reversal_risk=regime_feats.get("reversal_risk", 0.0),
                drawdown_pressure=regime_feats.get("drawdown_pressure", 0.0),
                structure_alignment=regime_feats.get("structure_alignment", 0.5),
                volatility_expansion=regime_feats.get("volatility_expansion", 0.0),
                dominant_regime=regime_post_30d.get("dominant_regime", "range") if regime_post_30d else "range",
                breakdown_prob=(regime_post_30d or {}).get("probabilities", {}).get("breakdown", 0.05),
            ))
            _struct_v2_30d = _structure_engine.evaluate(StructureInputs(
                trend_strength=regime_feats.get("trend_strength", 0.5),
                trend_persistence=regime_feats.get("trend_persistence", 0.5),
                momentum=regime_feats.get("exhaustion", 0.5),
                structure_alignment=regime_feats.get("structure_alignment", 0.5),
                volatility_expansion=regime_feats.get("volatility_expansion", 0.0),
                drawdown_pressure=_drr_out_30d.drawdown_pressure,
                reversal_risk=_drr_out_30d.reversal_risk,
                breakdown_risk=_drr_out_30d.breakdown_risk,
                regime=regime_post_30d.get("dominant_regime", "range") if regime_post_30d else "range",
            ))
            _w30 = STRUCTURE_V2_BLEND
            _bull_struct_30d = (1 - _w30) * _bull_struct_30d_legacy + _w30 * _struct_v2_30d.bullish_structure
            _bear_struct_30d = (1 - _w30) * _bear_struct_30d_drr + _w30 * _struct_v2_30d.bearish_structure
        else:
            _bull_struct_30d = _bull_struct_30d_legacy
            _bear_struct_30d = _bear_struct_30d_drr

        _ctx_align_30d = (ctx_features_30d.get("trend_strength", 0.5) * ctx_features_30d.get("trend_persistence", 0.5)) if ctx_features_30d else 0.5
        _neg_ctx_30d = ctx_features_30d.get("drawdown_pressure", 0.0) if ctx_features_30d else 0.0

        # ── Interaction Layer V1 (Shadow Mode) — 30D ──
        if INTERACTION_ENABLED:
            try:
                if _struct_v2_30d:
                    _il_state_30d = _struct_v2_30d.structure_state
                    _il_clarity_30d = _struct_v2_30d.structure_clarity
                    _il_regime_30d = (regime_post_30d or {}).get("dominant_regime", "range")
                else:
                    _il_state_30d = "mixed"
                    _il_clarity_30d = 0.3
                    _il_regime_30d = regime.lower() if regime else "range"

                _il_inp_30d = _InteractionInputs(
                    structure_state=_il_state_30d,
                    structure_clarity=_il_clarity_30d,
                    bullish_structure=_bull_struct_30d,
                    bearish_structure=_bear_struct_30d,
                    dominant_regime=_il_regime_30d,
                    regime_entropy=regime_entropy_30d,
                    dominant_scenario=_dom_scenario_30d,
                    bullish_prob=_bull_prob_30d,
                    base_prob=_base_prob_30d,
                    bearish_prob=_bear_prob_30d,
                    calibrated_confidence=confidence_direction,
                    expected_move_pct=abs(move_pct),
                )
                _interaction_output_30d = _interaction_layer.evaluate(_il_inp_30d)
                print(f"[INTERACTION_V1] {asset}/{horizon_key}: state={_interaction_output_30d.interaction_state} align={_interaction_output_30d.alignment_score:.3f} conflict={_interaction_output_30d.conflict_score:.3f} conf_mod={_interaction_output_30d.confidence_modifier:.3f} bias_mod={_interaction_output_30d.decision_bias_modifier:.3f}")

                # Stage 2: Apply confidence modifier (when enabled)
                if INTERACTION_USE_CONFIDENCE and not INTERACTION_KILL_SWITCH:
                    _conf_before_30d = confidence_direction
                    _conf_scale_30d = INTERACTION_CONF_SCALE.get(horizon_key, 0.65)
                    # V2 state-aware blending (when enabled)
                    if META_V2_ENABLED and META_V2_USE_CONFIDENCE:
                        _state_group_30d = resolve_state_group(_interaction_output_30d.interaction_state)
                        _v2_snap_30d = getattr(_interaction_layer, '_meta_v2_snap', {}).get(horizon_key)
                        if _v2_snap_30d and _state_group_30d in _v2_snap_30d.conf_scales:
                            _v2_scale_30d = _v2_snap_30d.conf_scales[_state_group_30d]
                            _conf_scale_30d = MetaCalibrationLayerV2.compute_blend(
                                _conf_scale_30d, _v2_scale_30d, META_V2_BLEND_WITH_V1,
                            )
                    _raw_delta_30d = _conf_scale_30d * _interaction_output_30d.confidence_modifier
                    _raw_delta_30d = max(INTERACTION_CONF_PRECLIP[0], min(INTERACTION_CONF_PRECLIP[1], _raw_delta_30d))
                    confidence_direction = max(0.05, min(0.95, confidence_direction + _raw_delta_30d))
                    _conf_after_30d = confidence_direction
                    print(f"[STAGE2] {asset}/{horizon_key}: conf {_conf_before_30d:.4f} → {_conf_after_30d:.4f} (Δ={_conf_after_30d - _conf_before_30d:+.4f}, scale={_conf_scale_30d:.3f})")

            except Exception as e:
                print(f"[INTERACTION_V1] {asset}/{horizon_key}: shadow error ({e})")

        d_inputs_30d = DecisionInputs(
            asset=asset,
            horizon=horizon_key,
            calibrated_confidence=confidence_direction,
            forecast_direction=_forecast_dir_30d,
            regime_entropy=regime_entropy_30d,
            regime_gap=_compute_regime_gap(regime_probs_30d),
            dominant_regime=regime.lower() if regime else "range",
            structure_strength=structure_features.get("structure_stability_score", 0.5) if structure_features else 0.5,
            bullish_structure=_bull_struct_30d,
            bearish_structure=_bear_struct_30d,
            context_alignment=_ctx_align_30d,
            negative_context=_neg_ctx_30d,
            expected_move_pct=abs(move_pct),
            dominant_scenario=_dom_scenario_30d,
            dominant_scenario_prob=_dom_prob_30d,
            bullish_prob=_bull_prob_30d,
            base_prob=_base_prob_30d,
            bearish_prob=_bear_prob_30d,
        )
        decision_output_30d = _decision_layer.decide(d_inputs_30d)
        legacy_direction = decision_output_30d.direction
        _neutral_reason_30d = ""
        if decision_output_30d.direction == "NEUTRAL" and decision_output_30d.rationale:
            _neutral_reason_30d = f" reason=[{', '.join(decision_output_30d.rationale)}]"
        print(f"[DECISION_V1] {asset}/{horizon_key}: {decision_output_30d.direction} mode={decision_output_30d.decision_mode} str={decision_output_30d.decision_strength:.3f} bull_s={d_inputs_30d.bullish_structure:.3f} bear_s={d_inputs_30d.bearish_structure:.3f} bull_p={d_inputs_30d.bullish_prob:.3f} bear_p={d_inputs_30d.bearish_prob:.3f} entropy={d_inputs_30d.regime_entropy:.3f}{_neutral_reason_30d}")
    except Exception as e:
        print(f"[DECISION_V1] {asset}/{horizon_key}: fallback to legacy ({e})")

    # D1: Decision Layer audit (30D)
    if decision_output_30d:
        audit["decisionLayer"] = {
            "direction": decision_output_30d.direction,
            "mode": decision_output_30d.decision_mode,
            "strength": decision_output_30d.decision_strength,
            "confidence": decision_output_30d.decision_confidence,
            "rationale": decision_output_30d.rationale,
            "scores": decision_output_30d.audit,
        }
        # Structure V2 audit (30D)
        if _struct_v2_30d:
            audit["structure_v2"] = {
                "bullish": round(_struct_v2_30d.bullish_structure, 4),
                "bearish": round(_struct_v2_30d.bearish_structure, 4),
                "clarity": round(_struct_v2_30d.structure_clarity, 4),
                "state": _struct_v2_30d.structure_state,
                "components": _struct_v2_30d.audit,
                "blend_weight": STRUCTURE_V2_BLEND,
            }

    # Interaction Layer V1 audit (shadow) — 30D
    if _interaction_output_30d:
        _state_grp_30d = resolve_state_group(_interaction_output_30d.interaction_state)
        _i_audit_30d = {
            "state": _interaction_output_30d.interaction_state,
            "state_group": _state_grp_30d,
            "alignment_score": _interaction_output_30d.alignment_score,
            "conflict_score": _interaction_output_30d.conflict_score,
            "confidence_modifier": _interaction_output_30d.confidence_modifier,
            "decision_bias_modifier": _interaction_output_30d.decision_bias_modifier,
            "scenario_mods": {
                "bullish": _interaction_output_30d.bullish_scenario_modifier,
                "base": _interaction_output_30d.base_scenario_modifier,
                "bearish": _interaction_output_30d.bearish_scenario_modifier,
            },
            "rationale": _interaction_output_30d.rationale,
            "polarity": _interaction_output_30d.audit,
        }
        try:
            _i_audit_30d["confidence_before_interaction"] = round(_conf_before_30d, 4)
            _i_audit_30d["confidence_after_interaction"] = round(_conf_after_30d, 4)
            _i_audit_30d["confidence_delta"] = round(_conf_after_30d - _conf_before_30d, 4)
        except NameError:
            pass
        audit["interaction"] = _i_audit_30d

    # ── Exchange Signal Adapter (30D) ──
    _exchange_db = db if db is not None else _get_db()
    _exchange_signal_data_30d = None
    try:
        exchange_ctx = _fetch_exchange_context(_exchange_db, asset)
        _exchange_signal_data_30d = build_exchange_signal(exchange_ctx)
        _decision_for_bias = {"direction": direction, "confidence": confidence}
        _decision_for_bias = apply_exchange_bias(_decision_for_bias, _exchange_signal_data_30d)
        audit["exchange_signal"] = _exchange_signal_data_30d
        audit["exchange_bias"] = _decision_for_bias.get("exchange_bias_audit", {})
        audit["exchange_context"] = exchange_ctx
    except Exception as exc:
        audit["exchange_signal_error"] = str(exc)

    # ── Forecast V2 (shadow mode — C3, 30D) ──
    try:
        from forecast.forecast_v2 import compute_forecast_v2
        _fv2_result_30d = compute_forecast_v2(
            base_score=score_final,
            exchange_signal=_exchange_signal_data_30d or {},
            audit=audit,
            features=features,
            price=price,
            db=_exchange_db,
            asset=asset,
            horizon=horizon,
        )
        audit["forecast_v2"] = _fv2_result_30d
        audit["forecast_v1_score"] = round(score_final, 6)
        audit["forecast_v2_score"] = _fv2_result_30d.get("final_score", score_final)
    except Exception as exc:
        audit["forecast_v2_error"] = str(exc)

    # ── Decision V2 (shadow mode — C2, 30D) ──
    _decision_base_30d = audit.get("forecast_v2_score", score_final) if audit.get("forecast_v2") else score_final
    try:
        from forecast.decision_v2 import compute_decision_v2
        _v2_result_30d = compute_decision_v2(
            base_score=_decision_base_30d,
            exchange_signal=_exchange_signal_data_30d or {},
            audit=audit,
            v1_direction=legacy_direction,
            v1_confidence=confidence,
        )
        audit["decision_v2"] = _v2_result_30d
    except Exception as exc:
        audit["decision_v2_error"] = str(exc)

    # ── System Convergence: V2 Live Routing (30D) ──
    _final_direction_30d = legacy_direction
    _final_confidence_30d = confidence
    try:
        from forecast.convergence import apply_v2_to_forecast
        _fv2_30d = audit.get("forecast_v2", {})
        _dv2_30d = audit.get("decision_v2", {})
        _final_direction_30d, _final_confidence_30d, _, _conv_audit_30d = apply_v2_to_forecast(
            forecast_id=forecast_id,
            v1_direction=legacy_direction,
            v1_confidence=confidence,
            v1_score=score_final,
            forecast_v2_result=_fv2_30d,
            decision_v2_result=_dv2_30d,
        )
        audit["convergence"] = _conv_audit_30d
    except Exception as exc:
        audit["convergence_error"] = str(exc)

    # ── System Aggregator (shadow mode — BLOCK 3, 30D) ──
    try:
        from forecast.system.aggregator import (
            AggregatorInputs, compute_aggregated_signal, aggregator_to_audit,
        )
        from forecast.system.sentiment_adapter import fetch_sentiment_for_asset
        from forecast.system.fractal_adapter import fetch_fractal_signal

        _agg_db_30d = db if db is not None else _get_db()
        _sentiment_30d = fetch_sentiment_for_asset(_agg_db_30d, asset)
        _fractal_30d = fetch_fractal_signal(_agg_db_30d, asset)

        _dv2_30d_r = audit.get("decision_v2", {}) or {}
        _fv2_score_30d = audit.get("forecast_v2_score", score_final)
        _micro_bias_30d = (_exchange_signal_data_30d or {}).get("micro_bias", 0)
        _regime_dir_30d = _dv2_30d_r.get("regime_direction", "RANGE")
        _conflict_30d = (audit.get("interaction", {}) or {}).get("conflict_score", 0) or 0

        _agg_input_30d = AggregatorInputs(
            forecast_score=_fv2_score_30d,
            exchange_bias=_micro_bias_30d,
            sentiment_score=_sentiment_30d["score"],
            sentiment_confidence=_sentiment_30d["confidence"],
            fractal_signal=_fractal_30d["signal"],
            fractal_confidence=_fractal_30d["confidence"],
            regime=_regime_dir_30d,
            conflict_score=_conflict_30d,
            horizon="30D",
        )
        _agg_output_30d = compute_aggregated_signal(_agg_input_30d)
        audit["aggregator_v1"] = aggregator_to_audit(_agg_output_30d)
        audit["aggregator_v1"]["sentiment_input"] = _sentiment_30d
        audit["aggregator_v1"]["fractal_input"] = _fractal_30d

        # ── Controlled Live Routing (30D) ──
        from forecast.system.aggregator import apply_aggregator_to_forecast
        _agg_live_30d = apply_aggregator_to_forecast(
            forecast_id=str(audit.get("signalId", "")),
            current_direction=_final_direction_30d,
            current_confidence=_final_confidence_30d,
            current_score=score_final,
            agg_output=_agg_output_30d,
            exchange_bias=_micro_bias_30d,
            horizon="30D",
        )
        audit["aggregator_live"] = _agg_live_30d["telemetry"]
        if _agg_live_30d["telemetry"]["used"]:
            _final_direction_30d = _agg_live_30d["direction"]
            _final_confidence_30d = _agg_live_30d["confidence"]
            score_final = _agg_live_30d["score"]
    except Exception as exc:
        audit["aggregator_error"] = str(exc)

    # ── Decision Trace (PLO enrichment — read-only logging, 30D) ──
    audit["decision_trace"] = {
        "base_score": round(score_final, 6),
        "exchange_bias": round((_exchange_signal_data_30d or {}).get("micro_bias", 0), 4),
        "forecast_v2_score": round(audit.get("forecast_v2_score", score_final), 6),
        "decision_v2_direction": (audit.get("decision_v2") or {}).get("direction", "N/A"),
        "decision_v2_confidence": (audit.get("decision_v2") or {}).get("confidence", 0),
        "thresholds": {
            "long": (audit.get("decision_v2") or {}).get("thresholds", {}).get("long", 0.10),
            "short": (audit.get("decision_v2") or {}).get("thresholds", {}).get("short", -0.10),
            "dynamic": (audit.get("decision_v2") or {}).get("thresholds", {}).get("dynamic", False),
        },
        "regime_direction": (audit.get("decision_v2") or {}).get("regime_direction", "UNKNOWN"),
        "reversal_signal": (audit.get("decision_v2") or {}).get("reversal_signal", False),
        "anti_trap": (audit.get("decision_v2") or {}).get("anti_trap_applied", False),
        "final_direction": _final_direction_30d,
        "final_confidence": round(_final_confidence_30d, 4),
        "system_version": (audit.get("convergence") or {}).get("system_version", "V1"),
        "aggregator_direction": (audit.get("aggregator_v1") or {}).get("direction", "N/A"),
        "aggregator_confidence": (audit.get("aggregator_v1") or {}).get("confidence", 0),
    }

    return ForecastRecord(
        id=forecast_id,
        asset=asset,
        symbol=f"{asset}USDT",
        horizon=horizon,
        horizonDays=horizon_days,
        runId=run_id,
        createdAt=now_ms,
        createdBucket=bucket,
        evaluateAfter=evaluate_after,
        entryPrice=round(price, 2),
        targetPrice=target_price,
        expectedMovePct=move_pct,
        direction=_final_direction_30d,
        confidence=_final_confidence_30d,
        confidenceRaw=round(confidence_raw, 4),
        modelVersion=model_version,
        featuresHash=features["features_hash"],
        immutableHash=immutable_hash,
        dataWindowEnd=now_ms,
        source="scheduler",
        forecastType="band",
        medianTarget=median_target,
        bandCoreLow=band_core_low,
        bandCoreHigh=band_core_high,
        bandWideLow=band_wide_low,
        bandWideHigh=band_wide_high,
        directionClass=direction,
        confidenceDirection=round(confidence_direction, 4),
        confidenceTarget=round(confidence_target, 4),
        degraded=degraded,
        audit=audit,
        scenarios=scenario_set,
    )


def _to_legacy_direction(direction_class: str) -> str:
    """Map 5-state direction to legacy 3-state for backward compatibility."""
    if direction_class in ("STRONG_BULL", "MILD_BULL"):
        return "LONG"
    if direction_class in ("STRONG_BEAR", "MILD_BEAR"):
        return "SHORT"
    return "NEUTRAL"
