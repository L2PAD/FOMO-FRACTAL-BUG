"""
Decision Layer V1 — Engine
============================
Block D1: Translates truth layer outputs into disciplined directional decisions.

Replaces the naive direction classifier with a multi-factor scoring system:
  - Long score / Short score / Neutral pressure
  - Hard neutral guardrails (entropy, scenario flatness, tiny moves)
  - Strong directional rules (scenario dominance + low entropy + structure)
  - Normal eligibility gates (directional_score, spread, scenario_prob, entropy, move)
  - Decision modes: directional / cautious_directional / neutral_filter

Target output profile:
  NEUTRAL → 45-65% (down from 81%)
  LONG+SHORT → 35-55%
  FP should NOT explode
"""

from forecast.decision.contracts import DecisionInputs, DecisionOutput


# Move reference per horizon (for normalization)
MOVE_REF = {
    "24H": 2.5,
    "7D": 2.0,
    "30D": 4.0,
}

# Absolute minimum expected move to consider direction (per horizon)
RAW_MOVE_FLOOR = {
    "24H": 1.5,
    "7D": 0.3,
    "30D": 0.5,
}

# Minimum move for strong directional rules (higher bar)
STRONG_MOVE_MIN = {
    "24H": 1.5,
    "7D": 0.5,
    "30D": 1.0,
}


class DecisionLayerV1:

    def decide(self, x: DecisionInputs) -> DecisionOutput:
        move_ref = MOVE_REF.get(x.horizon, 6.0)
        norm_move = self._normalize_move(x.expected_move_pct, move_ref)
        ambiguity = 1.0 - abs(x.bullish_prob - x.bearish_prob)

        long_score = (
            0.30 * x.bullish_prob
            + 0.20 * x.calibrated_confidence
            + 0.15 * x.bullish_structure
            + 0.15 * x.context_alignment
            + 0.10 * (1.0 - x.regime_entropy)
            + 0.10 * norm_move
        )

        short_score = (
            0.30 * x.bearish_prob
            + 0.20 * x.calibrated_confidence
            + 0.15 * x.bearish_structure
            + 0.15 * x.negative_context
            + 0.10 * (1.0 - x.regime_entropy)
            + 0.10 * norm_move
        )

        neutral_pressure = (
            0.35 * x.base_prob
            + 0.25 * x.regime_entropy
            + 0.20 * max(0.0, 1.0 - norm_move)
            + 0.20 * ambiguity
        )

        direction, mode = self._apply_rules(
            x, long_score, short_score, neutral_pressure, norm_move,
        )

        strength = max(long_score, short_score) if direction != "NEUTRAL" else neutral_pressure
        conf = self._decision_confidence(direction, long_score, short_score, neutral_pressure)

        rationale = self._build_rationale(
            x, direction, mode, long_score, short_score, neutral_pressure, norm_move,
        )

        return DecisionOutput(
            direction=direction,
            decision_strength=round(strength, 4),
            decision_confidence=round(conf, 4),
            decision_mode=mode,
            rationale=rationale,
            audit={
                "long_score": round(long_score, 4),
                "short_score": round(short_score, 4),
                "neutral_pressure": round(neutral_pressure, 4),
                "norm_move": round(norm_move, 4),
                "ambiguity": round(ambiguity, 4),
            },
        )

    # ── Private methods ──

    @staticmethod
    def _normalize_move(expected_move_pct: float, move_ref: float) -> float:
        return max(0.0, min(1.0, abs(expected_move_pct) / move_ref))

    def _apply_rules(
        self,
        x: DecisionInputs,
        long_score: float,
        short_score: float,
        neutral_pressure: float,
        norm_move: float,
    ) -> tuple:
        spread = abs(long_score - short_score)
        winner = "LONG" if long_score > short_score else "SHORT"
        directional_score = max(long_score, short_score)

        # ── Hard neutral filters ──

        # Raw move floor — even strong signals can't justify direction for tiny moves
        if x.expected_move_pct < RAW_MOVE_FLOOR.get(x.horizon, 0.3):
            return "NEUTRAL", "neutral_filter"

        if x.regime_entropy >= 0.78:
            return "NEUTRAL", "neutral_filter"

        if max(x.bullish_prob, x.base_prob, x.bearish_prob) < 0.40:
            return "NEUTRAL", "neutral_filter"

        if norm_move < 0.18:
            return "NEUTRAL", "neutral_filter"

        # ── Strong directional rules (require meaningful move) ──
        strong_min = STRONG_MOVE_MIN.get(x.horizon, 0.5)

        if (
            x.bullish_prob > 0.50
            and x.regime_entropy < 0.45
            and x.bullish_structure > 0.65
            and x.expected_move_pct >= strong_min
        ):
            return "LONG", "directional"

        if (
            x.bearish_prob > 0.50
            and x.regime_entropy < 0.45
            and x.bearish_structure > 0.65
            and x.expected_move_pct >= strong_min
        ):
            return "SHORT", "directional"

        # ── Normal eligibility ──
        if (
            directional_score > 0.36
            and spread > 0.04
            and x.dominant_scenario_prob > 0.35
            and x.regime_entropy < 0.72
            and norm_move > 0.15
        ):
            if directional_score > 0.55 and x.regime_entropy < 0.45:
                return winner, "directional"
            return winner, "cautious_directional"

        return "NEUTRAL", "neutral_filter"

    @staticmethod
    def _decision_confidence(
        direction: str,
        long_score: float,
        short_score: float,
        neutral_pressure: float,
    ) -> float:
        if direction == "NEUTRAL":
            return min(0.9, 0.55 + 0.35 * neutral_pressure)

        directional_score = max(long_score, short_score)
        spread = abs(long_score - short_score)
        return min(0.9, 0.50 + 0.30 * directional_score + 0.20 * spread)

    @staticmethod
    def _build_rationale(
        x: DecisionInputs,
        direction: str,
        mode: str,
        long_score: float,
        short_score: float,
        neutral_pressure: float,
        norm_move: float,
    ) -> list:
        out = []

        if direction == "LONG":
            if x.bullish_prob > 0.50:
                out.append("bullish scenario is dominant")
            if x.bullish_structure > 0.65:
                out.append("bullish structure remains supportive")
            if x.regime_entropy < 0.45:
                out.append("regime remains relatively clear")
            if norm_move > 0.50:
                out.append("expected move is significant")

        elif direction == "SHORT":
            if x.bearish_prob > 0.50:
                out.append("bearish scenario is dominant")
            if x.bearish_structure > 0.65:
                out.append("bearish structure remains elevated")
            if x.negative_context > 0.55:
                out.append("negative context remains active")
            if norm_move > 0.50:
                out.append("expected move is significant")

        else:
            if x.regime_entropy > 0.70:
                out.append("market state remains ambiguous")
            if x.base_prob > 0.40:
                out.append("base scenario still dominates")
            if norm_move < 0.25:
                out.append("expected move remains too small for directional conviction")
            if abs(x.bullish_prob - x.bearish_prob) < 0.10:
                out.append("directional probabilities are too balanced")

        return out
