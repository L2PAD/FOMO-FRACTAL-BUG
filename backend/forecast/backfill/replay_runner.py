"""
Replay Runner
===============
Runs triple pipeline (v4.1 base / v4.1.1 single-scale / v4.1.3 adaptive multi-scale)
on a point-in-time snapshot.
All pipelines use identical features/baselines/regime — only structure differs.
"""

import hashlib

from forecast.v41_config import (
    classify_direction,
    calibrate_confidence,
    REGIME_SHRINKAGE,
    DEGRADATION_CONFIG,
)
from forecast.structure.extractor import StructureFeatureExtractor
from forecast.structure.optimizer import StructureWeightOptimizer
from forecast.structure.multi_scale_extractor import extract_multiscale
from forecast.structure.pullback_detector import detect_mode
from forecast.structure.major_minor_fusion import fuse as fuse_major_minor, apply_multiscale_guards
from forecast.structure.direction_override_gate import DirectionOverrideGate
from forecast.context.context_feature_builder import build_context_features
from forecast.context.context_phase_classifier import classify_phase
from forecast.context.context_adjustment_engine import apply_context
from forecast.regime.regime_feature_builder import build_regime_features
from forecast.regime.regime_probability_engine import compute_regime_probabilities
from forecast.regime.regime_postprocessor import postprocess_regime
from forecast.regime.regime_adjustment_engine import apply_regime_adjustments

_extractor = StructureFeatureExtractor()
_optimizer = StructureWeightOptimizer()
_override_gate = DirectionOverrideGate()


def run_dual_replay(snapshot: dict, target_version: str = "v4.2.0") -> dict:
    """
    Run v4.1 (base), v4.1.1 (single-scale), and v4.1.3 (adaptive + override) on the same snapshot.
    Primary comparison: base vs v4.1.3 (or v4.2.0 if target_version includes context).
    Supplementary: v4.1.1 for triple comparison table.

    target_version:
      "v4.1.3" — structure + override only (no context layer)
      "v4.2.0" — structure + override + market context layer
    """
    apply_context_layer = target_version >= "v4.2.0"
    horizon = snapshot["horizon"]
    features = snapshot["features"]
    baseline = snapshot["baseline"]
    regime = snapshot["regime"]
    regime_conf = snapshot["regime_confidence"]
    perf = snapshot["recent_perf"]
    prices = snapshot["prices"]

    # Deterministic seed matching the original generator
    seed_str = f"{snapshot['as_of']}:{horizon}:{snapshot['asset']}:v4.1.0"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    perturbation = ((seed % 1000) / 1000 - 0.5) * 0.02

    regime_shrinkage = REGIME_SHRINKAGE.get(regime, 0.82)

    if horizon == "30D":
        base_result = _replay_30d(features, baseline, regime_shrinkage, perturbation, perf)
    else:
        base_result = _replay_7d_24h(features, baseline, regime_shrinkage, perturbation, perf)

    # ── v4.1.1: Single-scale structure ──
    sf_v411 = _extractor.extract_from_prices(prices)
    delta_v411 = _optimizer.compute_delta(horizon, sf_v411, base_result["score_raw"])

    score_v411 = delta_v411["score_after_structure"]
    dir_v411 = classify_direction(score_v411)
    s_v411, m_v411, c_v411 = _apply_degradation(
        score_v411, base_result["move_raw"], base_result["confidence_raw"], perf,
    )

    # ── v4.1.3: Adaptive multi-scale + guards + override ──
    try:
        multiscale = extract_multiscale(prices)
        mode_info = detect_mode(multiscale["major"], multiscale["minor"])
        fused_features = fuse_major_minor(
            multiscale["major"], multiscale["minor"], mode_info, base_result["score_raw"],
        )

        delta_v413 = _optimizer.compute_delta(horizon, fused_features, base_result["score_raw"])
        delta_v413 = apply_multiscale_guards(delta_v413, mode_info, base_result["score_raw"])

        # v4.1.3: Direction Override Gate (7D/24H only)
        override_result = {"override_allowed": False, "reason": "30D_disabled"}

        # v4.2.0: Compute context phase BEFORE override (for v4.2.1 modulation)
        ctx_features = None
        ctx_phase = None
        context_meta = None
        if apply_context_layer:
            try:
                ctx_features = build_context_features(features, fused_features, {
                    "major": multiscale["major"], "minor": multiscale["minor"],
                    "mode": mode_info["mode"],
                })
                ctx_phase = classify_phase(ctx_features)
            except Exception:
                pass

        if horizon != "30D":
            override_result = _override_gate.maybe_override(
                base_score=delta_v413["score_after_structure"],
                fused_structure=fused_features,
                mode=mode_info["mode"],
                major_fallback_used=multiscale.get("major_fallback_used", False),
            )
            # v4.2.1: Phase-aware modulation (only when context is available)
            if override_result["override_allowed"] and ctx_phase and apply_context_layer:
                override_result = _override_gate.modulate_override(
                    override_result, ctx_phase["market_phase"],
                )
            if override_result["override_allowed"]:
                delta_v413["score_after_structure"] = override_result["override_score"]

        score_v413 = delta_v413["score_after_structure"]

        # v4.2.0: Apply context confidence adjustments (after override)
        if apply_context_layer and ctx_features and ctx_phase:
            try:
                ctx_adj = apply_context(
                    score=score_v413, conf_dir=0.5, conf_tgt=0.5, band_width=1.0,
                    ctx=ctx_features, phase=ctx_phase,
                )
                score_v413 = ctx_adj["score"]
                context_meta = {
                    "features": ctx_features,
                    "phase": ctx_phase["market_phase"],
                    "context_confidence": ctx_phase["context_confidence"],
                    "adjustments": ctx_adj["adjustments"],
                }
            except Exception:
                pass

        # v4.3.0: Regime Engine V2 (after context, confidence-only)
        apply_regime_layer = target_version >= "v4.3.0"
        regime_meta = None
        regime_conf_mult = 1.0
        if apply_context_layer and ctx_features and ctx_phase:
            try:
                regime_feats = build_regime_features(
                    features, fused_features, ctx_features,
                    {"major": multiscale["major"], "minor": multiscale["minor"],
                     "mode": mode_info["mode"]},
                )
                regime_probs = compute_regime_probabilities(regime_feats,
                    context_phase=ctx_phase["market_phase"] if ctx_phase else "mixed_range")
                regime_post = postprocess_regime(regime_probs)
                regime_meta = {
                    "features": regime_feats,
                    "dominant_regime": regime_post["dominant_regime"],
                    "regime_confidence": regime_post["regime_confidence"],
                    "regime_entropy": regime_post["regime_entropy"],
                    "probabilities": regime_post["probabilities"],
                    "flags": regime_post["flags"],
                }
                # v4.3.0: Apply regime adjustments to confidence
                if apply_regime_layer:
                    regime_adj = apply_regime_adjustments(
                        score=score_v413,
                        conf_dir=0.5,
                        conf_tgt=0.5,
                        band_mult=1.0,
                        regime=regime_post,
                        regime_features=regime_feats,
                        context_phase=ctx_phase["market_phase"] if ctx_phase else None,
                    )
                    regime_conf_mult = regime_adj["adjustments"]["conf_dir_mult"]
                    regime_meta["adjustments"] = regime_adj["adjustments"]
            except Exception:
                pass

        dir_v413 = classify_direction(score_v413)
        # Apply regime confidence modulation before degradation
        conf_raw_for_degrad = base_result["confidence_raw"] * regime_conf_mult
        s_v413, m_v413, c_v413 = _apply_degradation(
            score_v413, base_result["move_raw"], conf_raw_for_degrad, perf,
        )

        multiscale_meta = {
            "mode": mode_info["mode"],
            "pullback_confidence": mode_info["pullback_confidence"],
            "major_dominant": mode_info["major_dominant"],
            "minor_counter_trend": mode_info.get("minor_counter_trend", False),
            "reversal_candidate": mode_info.get("reversal_candidate", False),
            "multiscale_guards": delta_v413.get("multiscale_guards", []),
            "major_profile_used": multiscale.get("major_profile_used", "strict"),
            "major_fallback_used": multiscale.get("major_fallback_used", False),
            "override": override_result,
            "context": context_meta,
            "regime": regime_meta,
        }
    except Exception:
        # Fallback: v4.1.3 = v4.1.1 (single-scale) if multi-scale fails
        score_v413 = score_v411
        dir_v413 = dir_v411
        s_v413, m_v413, c_v413 = s_v411, m_v411, c_v411
        fused_features = sf_v411
        delta_v413 = delta_v411
        multiscale_meta = {"mode": "fallback_single_scale"}
        override_result = {"override_allowed": False, "reason": "fallback"}

    return {
        "base": {
            "score": round(base_result["score_raw"], 6),
            "score_final": round(base_result["score_final"], 6),
            "direction": base_result["direction"],
            "confidence": round(base_result["confidence"], 4),
            "move_pct": round(base_result["move_pct"], 4),
        },
        "structure": {
            "score": round(score_v413, 6),
            "score_final": round(s_v413, 6),
            "direction": dir_v413,
            "confidence": round(c_v413, 4),
            "move_pct": round(m_v413 * 100, 4),
        },
        "v411": {
            "score": round(score_v411, 6),
            "score_final": round(s_v411, 6),
            "direction": dir_v411,
            "confidence": round(c_v411, 4),
            "move_pct": round(m_v411 * 100, 4),
        },
        "structure_features": fused_features,
        "structure_features_v411": sf_v411,
        "structure_delta": {
            "raw_delta": delta_v413.get("raw_delta", 0),
            "capped_delta": delta_v413.get("capped_delta", 0),
            "sign_flip_allowed": delta_v413.get("sign_flip_allowed", False),
            "multiscale_guards": delta_v413.get("multiscale_guards", []),
        },
        "structure_delta_v411": {
            "raw_delta": delta_v411["raw_delta"],
            "capped_delta": delta_v411["capped_delta"],
            "sign_flip_allowed": delta_v411["sign_flip_allowed"],
        },
        "multiscale_meta": multiscale_meta,
        "meta": {
            "regime": regime,
            "regime_confidence": regime_conf,
            "baseline_source": baseline.get("baselineSource", "unknown"),
            "momentum": features["momentum"],
            "perturbation": perturbation,
        },
    }


def _replay_7d_24h(features, baseline, regime_shrinkage, perturbation, perf):
    """Replay 7D/24H pipeline (without structure)."""
    momentum = features["momentum"]

    bull_score = 0.5 + momentum * 8 + perturbation
    bull_score = max(0.05, min(0.95, bull_score))
    directional_score = (bull_score - 0.5) * 2.0
    score_after_regime = directional_score * regime_shrinkage
    score_raw = score_after_regime

    direction = classify_direction(score_raw)

    mean_return = baseline.get("meanReturn", 0.0)

    base_shrinkage = 0.75
    total_shrinkage = base_shrinkage * regime_shrinkage

    if direction in ("STRONG_BULL", "MILD_BULL"):
        move_raw = abs(mean_return) * total_shrinkage
    elif direction in ("STRONG_BEAR", "MILD_BEAR"):
        move_raw = -abs(mean_return) * total_shrinkage
    else:
        move_raw = 0.0

    if "MILD" in direction:
        move_raw *= 0.70

    confidence_raw = _compute_raw_confidence(baseline, regime_shrinkage, features)

    score_f, move_f, conf_f = _apply_degradation(score_raw, move_raw, confidence_raw, perf)

    return {
        "score_raw": score_raw,
        "score_final": score_f,
        "direction": direction,
        "move_raw": move_raw,
        "move_pct": move_f * 100,
        "confidence_raw": confidence_raw,
        "confidence": conf_f,
    }


def _replay_30d(features, baseline, regime_shrinkage, perturbation, perf):
    """Replay 30D pipeline (without structure)."""
    std_return = baseline.get("stdReturn", 0.05)
    median_return = baseline.get("medianReturn", 0.0)

    norm_median = median_return / max(std_return, 0.001)
    momentum_contrib = features["momentum"] * 4
    score_30d = norm_median * 0.6 + momentum_contrib * 0.4 + perturbation
    score_30d = max(-1.0, min(1.0, score_30d))

    score_after_regime = score_30d * regime_shrinkage
    score_raw = score_after_regime

    direction = classify_direction(score_raw)

    mean_return = baseline.get("meanReturn", 0.0)
    base_shrinkage = 0.75
    total_shrinkage = base_shrinkage * regime_shrinkage

    if direction in ("STRONG_BULL", "MILD_BULL"):
        move_raw = abs(mean_return) * total_shrinkage
    elif direction in ("STRONG_BEAR", "MILD_BEAR"):
        move_raw = -abs(mean_return) * total_shrinkage
    else:
        move_raw = 0.0

    if "MILD" in direction:
        move_raw *= 0.70

    confidence_raw = _compute_raw_confidence(baseline, regime_shrinkage, features)

    score_f, move_f, conf_f = _apply_degradation(score_raw, move_raw, confidence_raw, perf)

    return {
        "score_raw": score_raw,
        "score_final": score_f,
        "direction": direction,
        "move_raw": move_raw,
        "move_pct": move_f * 100,
        "confidence_raw": confidence_raw,
        "confidence": conf_f,
    }


def _compute_raw_confidence(baseline, regime_shrinkage, features):
    """Simplified confidence computation for replay."""
    dir_hit = baseline.get("dirHitMean", 0.5)
    vol = features["volatility"]
    vol_penalty = max(0.7, 1.0 - vol * 2)
    return dir_hit * regime_shrinkage * vol_penalty


def _apply_degradation(score, move, confidence, perf):
    """Apply soft degradation based on recent performance."""
    win_rate = perf.get("rollingWinRate", 0.5)
    count = perf.get("recentCount", 0)

    score_mult = 1.0
    move_mult = 1.0
    conf_mult = 1.0

    if count >= DEGRADATION_CONFIG["meta_min_samples"] and win_rate < DEGRADATION_CONFIG["meta_threshold"]:
        score_mult *= DEGRADATION_CONFIG["meta_score_factor"]
        move_mult *= DEGRADATION_CONFIG["meta_move_factor"]
        conf_mult *= DEGRADATION_CONFIG["meta_confidence_factor"]

    if count >= DEGRADATION_CONFIG["heavy_min_samples"] and win_rate < DEGRADATION_CONFIG["heavy_threshold"]:
        score_mult *= DEGRADATION_CONFIG["heavy_score_factor"]
        move_mult *= DEGRADATION_CONFIG["heavy_move_factor"]
        conf_mult *= DEGRADATION_CONFIG["heavy_confidence_factor"]

    return score * score_mult, move * move_mult, confidence * conf_mult
