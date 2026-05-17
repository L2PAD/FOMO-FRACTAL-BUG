"""
Structure Weight Optimizer V2.1 — Guarded Influence
=====================================================
Targeted fix based on backfill ROLLBACK verdict.

Root cause: In range/biasless markets (bias≈0), secondary signals
(momentum, stability, compression) create a net positive delta that
pushes directional bearish scores towards NEUTRAL.

V2.1 fixes:
  1. Neutralization Guard: structure cannot push MILD→NEUTRAL without
     strong reversal evidence
  2. Biasless Weight Downscale: secondary weights reduced 65% when bias≈0
  3. Supportive vs Corrective modes: different caps for aligned vs opposing
  4. Direction Preservation Floor: directional base score has minimum abs value

Key rules (unchanged):
  - Delta capped at MAX_STRUCTURE_DELTA (0.18)
  - Horizon multiplier gates influence (7D=full, 30D=60%, 24H=40%)
  - Sign-flip only with strong reversal evidence
"""

from forecast.structure.config import STRUCTURE_WEIGHTS, STRUCTURE_CONFIG

# V2.1 guard thresholds
BIASLESS_THRESHOLD = 0.15
BIASLESS_SECONDARY_MULT = 0.35
DIRECTIONAL_BASE_THRESHOLD = 0.20
DIRECTION_FLOOR_ABS = 0.20
CORRECTIVE_DELTA_CAP = 0.60


class StructureWeightOptimizer:
    """V2.1 Guarded influence — structure modifies score with safety rails."""

    def __init__(self, weights: dict | None = None, max_delta: float | None = None):
        self.weights = weights or dict(STRUCTURE_WEIGHTS)
        self.max_delta = max_delta or STRUCTURE_CONFIG["max_delta"]
        self.horizon_multiplier = STRUCTURE_CONFIG["horizon_multiplier"]
        self.cfg = STRUCTURE_CONFIG

    def compute_delta(self, horizon: str, sf: dict, base_score: float) -> dict:
        """
        Compute guarded structure delta.

        Pipeline:
          1. Detect mode (supportive / corrective / biasless)
          2. Compute raw delta with contextual weight gating
          3. Apply horizon multiplier + cap
          4. Neutralization guard (no MILD→NEUTRAL without reversal)
          5. Sign-flip guard
          6. Direction preservation floor
        """
        bias = sf.get("structure_bias_score", 0.0)

        # Step 1: Detect mode
        mode = self._detect_mode(base_score, bias)

        # Step 2: Compute raw delta with contextual weights
        raw_delta = self._compute_raw_delta(sf, mode)

        # Step 3: Horizon multiplier + cap
        h_mult = self.horizon_multiplier.get(horizon, 0.75)
        raw_delta *= h_mult

        # In corrective mode, further reduce delta magnitude
        if mode == "corrective":
            raw_delta *= CORRECTIVE_DELTA_CAP

        capped_delta = max(-self.max_delta, min(self.max_delta, raw_delta))

        # Step 4: Compute candidate score
        candidate_score = base_score + capped_delta

        # Step 5: Check for strong reversal evidence
        strong_reversal = self._has_strong_reversal(base_score, sf)

        # Step 6: Neutralization guard
        would_neutralize = self._would_neutralize(base_score, candidate_score)
        neutralization_blocked = False

        if would_neutralize and not strong_reversal:
            candidate_score = self._preserve_direction_floor(base_score, candidate_score)
            neutralization_blocked = True

        # Step 7: Sign-flip guard (unchanged from V2)
        sign_flip_allowed = strong_reversal and abs(base_score) < self.cfg["sign_flip_base_threshold"]

        if not sign_flip_allowed and self._would_flip_sign(base_score, candidate_score):
            if abs(base_score) < self.cfg["weak_base_threshold"]:
                candidate_score = 0.0
            else:
                candidate_score = base_score * self.cfg["weak_base_fallback_factor"]

        candidate_score = max(-1.0, min(1.0, candidate_score))

        return {
            "raw_delta": round(raw_delta, 6),
            "capped_delta": round(capped_delta, 6),
            "sign_flip_allowed": sign_flip_allowed,
            "score_after_structure": round(candidate_score, 6),
            "horizon_multiplier": h_mult,
            "mode": mode,
            "strong_reversal": strong_reversal,
            "neutralization_blocked": neutralization_blocked,
        }

    # ═══════════════════════════════════════════════════════
    # V2.1 Core Logic
    # ═══════════════════════════════════════════════════════

    def _detect_mode(self, base_score: float, bias: float) -> str:
        """
        Detect structure influence mode:
          - supportive: structure bias aligned with base direction
          - corrective: structure bias opposes base direction
          - biasless: structure has no clear directional bias (range)
        """
        if abs(bias) < BIASLESS_THRESHOLD:
            return "biasless"

        base_sign = 1 if base_score > 0 else (-1 if base_score < 0 else 0)
        bias_sign = 1 if bias > 0 else -1

        if base_sign == bias_sign or base_sign == 0:
            return "supportive"
        return "corrective"

    def _compute_raw_delta(self, sf: dict, mode: str) -> float:
        """
        Compute raw delta with contextual weight gating.
        In biasless mode: secondary signals (momentum, stability, compression)
        are downscaled by 65% to prevent over-neutralization.
        """
        w = self.weights
        bias = sf.get("structure_bias_score", 0.0)

        # Secondary weight multiplier: reduced when no clear bias
        sec_mult = BIASLESS_SECONDARY_MULT if mode == "biasless" else 1.0

        return (
            bias * w["bias"]
            + sf.get("structure_trend_score", 0.0) * w["trend"]
            + sf.get("structure_momentum_score", 0.0) * w["momentum"] * sec_mult
            - sf.get("structure_reversal_risk", 0.0) * w["reversal_risk"]
            - sf.get("structure_exhaustion_score", 0.0) * w["exhaustion"]
            + sf.get("structure_stability_score", 0.0) * w["stability"] * sec_mult
            + sf.get("structure_compression_score", 0.0) * w["compression"] * sec_mult
        )

    def _has_strong_reversal(self, base_score: float, sf: dict) -> bool:
        """
        Strong reversal evidence requires ALL of:
          - reversal_risk > 0.70
          - momentum > 0.45 AGAINST base direction
          - bias is not zero (has directional thesis)
        """
        reversal = sf.get("structure_reversal_risk", 0.0)
        momentum = sf.get("structure_momentum_score", 0.0)
        bias = sf.get("structure_bias_score", 0.0)

        if reversal <= self.cfg["sign_flip_reversal_threshold"]:
            return False
        if abs(momentum) <= self.cfg["sign_flip_momentum_threshold"]:
            return False
        if abs(bias) < BIASLESS_THRESHOLD:
            return False

        # Momentum must oppose base direction
        return self._momentum_opposes_base(base_score, momentum)

    def _would_neutralize(self, base_score: float, candidate_score: float) -> bool:
        """
        Check if structure would push a directional score into neutral zone.
        MILD_BEAR→NEUTRAL or MILD_BULL→NEUTRAL.
        """
        if abs(base_score) < DIRECTIONAL_BASE_THRESHOLD:
            return False  # Base wasn't clearly directional

        from forecast.v41_config import classify_direction
        base_dir = classify_direction(base_score)
        cand_dir = classify_direction(candidate_score)

        directional = {"STRONG_BULL", "MILD_BULL", "STRONG_BEAR", "MILD_BEAR"}
        return base_dir in directional and cand_dir == "NEUTRAL"

    def _preserve_direction_floor(self, base_score: float, candidate_score: float) -> float:
        """
        When neutralization is blocked, preserve minimum directional magnitude.
        STRONG→MILD is allowed. MILD→NEUTRAL is blocked.
        """
        if base_score > 0:
            return max(candidate_score, DIRECTION_FLOOR_ABS)
        if base_score < 0:
            return min(candidate_score, -DIRECTION_FLOOR_ABS)
        return candidate_score

    def _would_flip_sign(self, base_score: float, candidate_score: float) -> bool:
        """Check if candidate would flip the sign of base score."""
        if base_score == 0 or candidate_score == 0:
            return False
        return base_score * candidate_score < 0

    def _momentum_opposes_base(self, base_score: float, momentum: float) -> bool:
        """Check if momentum direction opposes base score direction."""
        if base_score > 0 and momentum < 0:
            return True
        if base_score < 0 and momentum > 0:
            return True
        return False
