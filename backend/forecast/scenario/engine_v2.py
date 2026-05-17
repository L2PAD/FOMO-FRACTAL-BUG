"""
Scenario Engine V2 — Block 9
==============================
Multi-path intelligence output for 30D forecasts.

Transforms truth layer inputs into structured scenario set:
  bullish / base / bearish with:
  - calibrated probabilities (softmax + Block 8.3)
  - target ranges (vol/entropy-aware)
  - path semantics (7 types)
  - confidence tags (strong/moderate/uncertain)
  - rationale (feature-grounded)
  - full audit trace

Phase 2: Calibration integration, dominant safeguard, logging.
"""

import math
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("scenario_engine_v2")


# ── Contracts ──

ScenarioName = str  # "bullish" | "base" | "bearish"
PathType = str      # continuation | grind_up | range_then_breakout | range_hold | distribution | breakdown | flush_then_recover
ConfidenceTag = str  # strong | moderate | uncertain


@dataclass
class TruthInputs:
    asset: str
    horizon: str
    spot_price: float
    direction: str
    calibrated_confidence: float
    regime_probs: dict
    dominant_regime: str
    regime_entropy: float
    regime_gap: float
    structure_strength: float
    bullish_structure: float
    bearish_structure: float
    context_alignment: float
    negative_context: float
    volatility_norm: float
    expected_move_pct: float
    range_state_score: float
    drawdown_pressure: float


@dataclass
class ScenarioSeed:
    name: str
    raw_weight: float
    structure_support: float
    regime_support: float
    context_support: float
    volatility_modifier: float
    neutrality_support: float = 0.0


@dataclass
class ScenarioRange:
    target_low: float
    target_high: float
    expected_move_pct: float
    normalized_width: float


@dataclass
class ScenarioNode:
    name: str
    probability: float
    target_low: float
    target_high: float
    expected_move_pct: float
    path_type: str
    confidence_tag: str
    rationale: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.name,
            "probability": round(self.probability, 4),
            "range": (round(self.expected_move_pct * 0.6, 2), round(self.expected_move_pct * 1.2, 2)) if self.expected_move_pct > 0 else (round(self.expected_move_pct * 1.2, 2), round(self.expected_move_pct * 0.6, 2)),
            "target_low": round(self.target_low, 2),
            "target_high": round(self.target_high, 2),
            "expected_move": round(self.expected_move_pct, 2),
            "path_type": self.path_type,
            "confidence_tag": self.confidence_tag,
            "narrative": "; ".join(self.rationale) if self.rationale else "scenario plausible under current conditions",
        }


# ── Calibrator Adapter (Block 8.3 → V2 interface) ──

class ScenarioCalibratorAdapter:
    """Wraps Block 8.3 calibration functions for ScenarioEngineV2."""

    def __init__(self, horizon: str = "30D", cache_ttl: int = 3600):
        self._horizon = horizon
        self._cache_ttl = cache_ttl
        self._calibration_map = None
        self._last_build = 0.0

    def _ensure_map(self):
        now = time.time()
        if self._calibration_map and (now - self._last_build < self._cache_ttl):
            return

        try:
            from exchange.calibration.scenario_calibrator import (
                build_scenario_dataset, build_calibration_map,
            )
            dataset = build_scenario_dataset(horizon=self._horizon)
            self._calibration_map = build_calibration_map(dataset)
            self._last_build = now
            logger.info(
                "Calibration map rebuilt: horizon=%s, status=%s, dataset_size=%d",
                self._horizon, self._calibration_map.get("status"), len(dataset),
            )
        except Exception as e:
            logger.warning("Failed to build calibration map: %s", e)
            self._calibration_map = None

    def calibrate(self, raw_probs: dict, context: dict = None) -> dict:
        """Apply piecewise calibration + renormalization."""
        self._ensure_map()
        if not self._calibration_map or self._calibration_map.get("status") != "OK":
            return raw_probs

        from exchange.calibration.scenario_calibrator import calibrate_scenario_probs
        return calibrate_scenario_probs(raw_probs, self._calibration_map)


# ── Engine ──

class ScenarioEngineV2:

    def __init__(self, temperature: float = 0.9, calibrator=None):
        self.temperature = temperature
        self.calibrator = calibrator

    def build(self, truth: TruthInputs) -> dict:
        """Main entry: truth → scenario output."""
        seeds = self._build_seeds(truth)
        raw_probs = self._compute_raw_probabilities(seeds)
        calibrated_probs = self._calibrate_probabilities(raw_probs, truth)
        calibration_applied = self.calibrator is not None and calibrated_probs != raw_probs
        ranges = self._build_ranges(truth, calibrated_probs, seeds)
        path_types = self._select_paths(truth)
        confidence_tags = self._assign_confidence_tags(truth, calibrated_probs, ranges)
        rationales = self._build_rationales(truth, path_types)

        scenarios = []
        for name in ["bullish", "base", "bearish"]:
            r = ranges[name]
            scenarios.append(ScenarioNode(
                name=name,
                probability=calibrated_probs[name],
                target_low=r.target_low,
                target_high=r.target_high,
                expected_move_pct=r.expected_move_pct,
                path_type=path_types[name],
                confidence_tag=confidence_tags[name],
                rationale=rationales[name],
            ))

        scenarios.sort(key=lambda s: s.probability, reverse=True)
        dominant = scenarios[0].name
        dominant_prob = scenarios[0].probability

        # Phase 2 safeguard: if dominant probability < 0.40 → force uncertain
        if dominant_prob < 0.40:
            for s in scenarios:
                s.confidence_tag = "uncertain"
            confidence_tags = {s.name: "uncertain" for s in scenarios}

        # Build output dict (compatible with existing format)
        scenario_list = [s.to_dict() for s in scenarios]
        spread = max(calibrated_probs.values()) - min(calibrated_probs.values())

        # Phase 2: Logging raw vs calibrated
        logger.info(
            "[SCENARIO_V2] asset=%s raw=%s cal=%s cal_applied=%s dominant=%s(%.3f) spread=%.1f%%",
            truth.asset,
            {k: round(v, 3) for k, v in raw_probs.items()},
            {k: round(v, 3) for k, v in calibrated_probs.items()},
            calibration_applied,
            dominant, dominant_prob, spread * 100,
        )

        return {
            "scenarios": scenario_list,
            "dominant": dominant,
            "spread": round(spread * 100, 2),
            "confidence_tag": confidence_tags[dominant],
            "engine_version": "v2",
            "_audit": {
                "raw_weights": {k: round(v.raw_weight, 4) for k, v in seeds.items()},
                "raw_probs": {k: round(v, 4) for k, v in raw_probs.items()},
                "calibrated_probs": {k: round(v, 4) for k, v in calibrated_probs.items()},
                "calibration_applied": calibration_applied,
                "temperature": self.temperature,
                "path_selection": path_types,
                "confidence_tags": confidence_tags,
                "range_engine": {
                    "expected_move_pct": truth.expected_move_pct,
                    "volatility_norm": truth.volatility_norm,
                    "entropy": truth.regime_entropy,
                },
            },
        }

    # ── Seeds ──

    def _build_seeds(self, truth: TruthInputs) -> dict[str, ScenarioSeed]:
        rp = truth.regime_probs or {}
        trend_prob = rp.get("trend", 0.0)
        range_prob = rp.get("range", 0.0)
        pullback_prob = rp.get("pullback", 0.0)
        transition_prob = rp.get("transition", 0.0)
        breakdown_prob = rp.get("breakdown", 0.0)

        entropy = truth.regime_entropy

        bull_regime = trend_prob + 0.6 * pullback_prob
        bear_regime = breakdown_prob + 0.5 * transition_prob
        base_regime = range_prob + 0.5 * transition_prob + 0.4 * entropy

        bullish_raw = (
            0.35 * truth.bullish_structure
            + 0.25 * bull_regime
            + 0.20 * truth.context_alignment
            + 0.20 * (1 - entropy)
        )

        base_raw = (
            0.40 * entropy
            + 0.30 * base_regime
            + 0.15 * truth.range_state_score
            + 0.15 * max(0.0, 1 - abs(truth.calibrated_confidence - 0.5) * 2)
        )

        bearish_raw = (
            0.35 * truth.bearish_structure
            + 0.25 * bear_regime
            + 0.20 * truth.negative_context
            + 0.20 * max(0.0, truth.volatility_norm)
        )

        # Guardrail: prevent base from eating directional signal
        if truth.calibrated_confidence > 0.55:
            base_raw *= 0.85
        if entropy < 0.4:
            base_raw *= 0.8

        return {
            "bullish": ScenarioSeed("bullish", bullish_raw, truth.bullish_structure, bull_regime, truth.context_alignment, truth.volatility_norm),
            "base": ScenarioSeed("base", base_raw, truth.structure_strength, base_regime, truth.range_state_score, truth.volatility_norm, truth.range_state_score),
            "bearish": ScenarioSeed("bearish", bearish_raw, truth.bearish_structure, bear_regime, truth.negative_context, truth.volatility_norm),
        }

    # ── Probabilities ──

    def _softmax(self, values: list[float], temperature: float) -> list[float]:
        scaled = [v / max(temperature, 1e-8) for v in values]
        m = max(scaled)
        exps = [math.exp(v - m) for v in scaled]
        z = sum(exps) + 1e-8
        return [e / z for e in exps]

    def _compute_raw_probabilities(self, seeds: dict[str, ScenarioSeed]) -> dict[str, float]:
        names = ["bullish", "base", "bearish"]
        values = [seeds[n].raw_weight for n in names]
        probs = self._softmax(values, self.temperature)
        return {n: p for n, p in zip(names, probs)}

    def _calibrate_probabilities(self, raw_probs: dict[str, float], truth: TruthInputs) -> dict[str, float]:
        if not self.calibrator:
            return raw_probs

        try:
            calibrated = self.calibrator.calibrate(raw_probs, {
                "entropy": truth.regime_entropy,
                "dominant_regime": truth.dominant_regime,
                "volatility_norm": truth.volatility_norm,
            })

            # Guardrail 1: Minimum probability floor (no scenario killed to zero)
            MIN_PROB = 0.05
            floored = False
            for k in calibrated:
                if calibrated[k] < MIN_PROB:
                    calibrated[k] = MIN_PROB
                    floored = True
            if floored:
                z = sum(calibrated.values()) + 1e-8
                calibrated = {k: v / z for k, v in calibrated.items()}

            # Guardrail 2: Anti-collapse — if spread too low, blend with raw
            spread = max(calibrated.values()) - min(calibrated.values())
            if spread < 0.03:
                alpha = 0.15
                blended = {k: (1 - alpha) * calibrated[k] + alpha * raw_probs[k] for k in raw_probs}
                z = sum(blended.values()) + 1e-8
                calibrated = {k: v / z for k, v in blended.items()}

            # Guardrail 3: Dominant direction preservation
            # If raw dominant != calibrated dominant AND raw was strong (>0.45),
            # blend to preserve signal (use strong alpha to ensure preservation)
            raw_dominant = max(raw_probs, key=raw_probs.get)
            cal_dominant = max(calibrated, key=calibrated.get)
            if raw_dominant != cal_dominant and raw_probs[raw_dominant] > 0.45:
                alpha = max(0.60, raw_probs[raw_dominant])
                blended = {k: alpha * raw_probs[k] + (1 - alpha) * calibrated[k] for k in raw_probs}
                z = sum(blended.values()) + 1e-8
                calibrated = {k: v / z for k, v in blended.items()}

            return calibrated
        except Exception as e:
            logger.warning("Calibration failed, using raw: %s", e)
            return raw_probs

    # ── Ranges ──

    def _build_ranges(self, truth: TruthInputs, probs: dict, seeds: dict) -> dict[str, ScenarioRange]:
        spot = truth.spot_price
        expected_move = max(0.01, abs(truth.expected_move_pct))
        entropy = truth.regime_entropy
        vol = max(0.0, truth.volatility_norm)

        width_mult = 1.0 + 0.25 * entropy + 0.20 * vol
        width_mult = min(width_mult, 1.35)  # cap
        if entropy < 0.35:
            width_mult *= 0.9

        bull_strength = seeds["bullish"].raw_weight
        bear_strength = seeds["bearish"].raw_weight
        neutrality = seeds["base"].neutrality_support

        bull_move = expected_move * (1.15 + 0.15 * bull_strength)
        base_move = expected_move * (0.60 + 0.10 * neutrality)
        bear_move = expected_move * (1.10 + 0.20 * bear_strength)

        bull_low = spot * (1 + max(0.02, bull_move * 0.55))
        bull_high = spot * (1 + bull_move * width_mult)

        base_low = spot * (1 - base_move * 0.35)
        base_high = spot * (1 + base_move * 0.45)

        bear_low = spot * (1 - bear_move * width_mult)
        bear_high = spot * (1 - max(0.02, bear_move * 0.45))

        norm_width = min(1.0, 0.5 * width_mult)

        return {
            "bullish": ScenarioRange(bull_low, bull_high, round(bull_move * 100, 2), norm_width),
            "base": ScenarioRange(base_low, base_high, round(base_move * 100, 2), min(1.0, norm_width * 0.75)),
            "bearish": ScenarioRange(bear_low, bear_high, round(-bear_move * 100, 2), norm_width),
        }

    # ── Paths ──

    def _select_paths(self, truth: TruthInputs) -> dict[str, str]:
        entropy = truth.regime_entropy
        dom = truth.dominant_regime
        vol = truth.volatility_norm

        # Bullish path
        if truth.bullish_structure > 0.7 and entropy < 0.35 and dom in ("trend", "pullback"):
            bull_path = "continuation"
        elif truth.bullish_structure > 0.55 and vol < 0.7:
            bull_path = "grind_up"
        else:
            bull_path = "range_then_breakout"

        # Base path
        if entropy > 0.65:
            base_path = "range_hold"
        elif vol > 0.8 and truth.drawdown_pressure > 0.5:
            base_path = "flush_then_recover"
        else:
            base_path = "range_then_breakout"

        # Bearish path
        if truth.bearish_structure > 0.7 and dom == "breakdown":
            bear_path = "breakdown"
        elif vol > 0.85 and truth.drawdown_pressure > 0.65:
            bear_path = "flush_then_recover"
        else:
            bear_path = "distribution"

        return {"bullish": bull_path, "base": base_path, "bearish": bear_path}

    # ── Confidence Tags ──

    def _assign_confidence_tags(self, truth: TruthInputs, probs: dict, ranges: dict) -> dict[str, str]:
        tags = {}
        for name, prob in probs.items():
            entropy_c = 1 - truth.regime_entropy
            width_c = 1 - min(1.0, ranges[name].normalized_width)
            strength = 0.5 * prob + 0.3 * entropy_c + 0.2 * width_c

            if prob > 0.50 and truth.regime_entropy < 0.40 and ranges[name].normalized_width < 0.55:
                tags[name] = "strong"
            elif strength >= 0.42:
                tags[name] = "moderate"
            else:
                tags[name] = "uncertain"
        return tags

    # ── Rationale ──

    def _build_rationales(self, truth: TruthInputs, paths: dict) -> dict[str, list[str]]:
        out = {"bullish": [], "base": [], "bearish": []}

        if truth.bullish_structure > 0.7:
            out["bullish"].append("trend structure remains intact")
        if truth.context_alignment > 0.6:
            out["bullish"].append("context remains supportive")
        if truth.regime_entropy < 0.4:
            out["bullish"].append("market state is relatively clear")
        if truth.dominant_regime == "trend":
            out["bullish"].append("trend regime supports continuation")

        if truth.regime_entropy > 0.65:
            out["base"].append("market state remains ambiguous")
        if truth.range_state_score > 0.55:
            out["base"].append("range behavior remains plausible")
        if paths["base"] == "flush_then_recover":
            out["base"].append("volatility allows two-way path risk")

        if truth.bearish_structure > 0.65:
            out["bearish"].append("downside structure risk remains elevated")
        if truth.negative_context > 0.55:
            out["bearish"].append("context pressure remains negative")
        if truth.dominant_regime == "breakdown":
            out["bearish"].append("regime remains vulnerable to breakdown continuation")
        if truth.drawdown_pressure > 0.5:
            out["bearish"].append("drawdown pressure present")

        for k in out:
            if not out[k]:
                out[k].append("scenario remains plausible under current conditions")
        return out
